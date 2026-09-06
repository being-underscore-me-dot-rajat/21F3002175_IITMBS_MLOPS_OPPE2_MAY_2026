# run.md — OPPE-2 End-to-End Runbook

Heart disease prediction, production deployment on GCP.
Everything below has been syntax- and run-tested. Follow the parts in order.

**Time budget:** ~75 minutes total. **Cost:** ~₹90–150 (US $1–2) if you tear
down the same day. The two cost drivers are the GKE nodes and the LoadBalancer.

**Design choices for cheapness:**

* GKE Standard **zonal** (not regional) cluster, **2 × `e2-small`**,
  `pd-standard` 32 GB disks, Managed Prometheus off.
* MLflow runs **inside the Workbench instance** on a **SQLite** backend and a
  local artifact folder — no Cloud SQL, no GCS bucket, no extra spend.
* The trained model is a 2.4 KB `joblib` file committed to git, so the CI image
  build needs no artifact registry pull, no MLflow server, no GCS credentials.
* Workload Identity Federation for CI — keyless, so no SA JSON key to leak.

---

## Part 0 — Prerequisites

| Thing | Value |
|---|---|
| Roll number | fill into `infra/config.sh` |
| GCP project | fill into `infra/config.sh` |
| Region / Zone | `us-central1` / `us-central1-a` |
| Repo name | `<ROLL>_IITMBS_MLOPS_OPPE2_MAY_2026` |

Open **Google Cloud Shell** (the `>_` icon, top-right of the console). Every
`gcloud` command in Parts 1 and 3 runs there.

---

## Part 1 — Deliverable 1: private repo *(mandatory, do this first)*

```bash
# In Cloud Shell. Replace ROLL with your roll number, e.g. 21f1000500
export ROLL=REPLACE_ME
export GH_USER=REPLACE_ME

gh auth login                          # follow the browser prompt
gh repo create "${ROLL}_IITMBS_MLOPS_OPPE2_MAY_2026" --private
gh api -X PUT "repos/${GH_USER}/${ROLL}_IITMBS_MLOPS_OPPE2_MAY_2026/collaborators/IITMBSMLOps" \
  -f permission=push
```

Then **verify the invite was accepted** at
`https://github.com/<GH_USER>/<ROLL>_IITMBS_MLOPS_OPPE2_MAY_2026/settings/access`
before your session ends. If it is still *Pending*, tell the course team.

Push this project into it:

```bash
cd oppe2
git init -b main
git add .
git commit -m "OPPE-2: heart disease MLOps deployment"
git remote add origin "https://github.com/${GH_USER}/${ROLL}_IITMBS_MLOPS_OPPE2_MAY_2026.git"
git push -u origin main
```

---

## Part 2 — Fill in your config

Edit `infra/config.sh` and replace the five `REPLACE_ME` values:

```bash
export PROJECT_ID="your-gcp-project-id"
export GITHUB_OWNER="your-github-username"
export ROLL_NUMBER="21f1000500"
export REGION="us-central1"
export ZONE="us-central1-a"
```

---

## Part 3 — Provision GCP

First: `source infra/config.sh` (the manual commands below rely on those variables).

**Fast path** (runs Part 3 in one go, ~10 min, mostly cluster creation):

```bash
bash infra/setup.sh
```

It prints the exact GitHub secrets/variables you need at the end. If you prefer
to run it step by step, here are the same commands.

### 3.1 Enable APIs

```bash
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  container.googleapis.com artifactregistry.googleapis.com \
  compute.googleapis.com notebooks.googleapis.com aiplatform.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com \
  logging.googleapis.com monitoring.googleapis.com cloudresourcemanager.googleapis.com
```

### 3.2 Artifact Registry (Docker)

```bash
gcloud artifacts repositories create heart-repo \
  --repository-format=docker \
  --location="$REGION" \
  --description="Heart disease API images"
```

### 3.3 Least-privilege node service account

GKE's default node identity is the over-permissioned Compute Engine default SA.
Use a scoped one instead — it also keeps Cloud Logging working for Deliverable 5.

```bash
gcloud iam service-accounts create gke-node-sa --display-name="GKE node SA"
NODE_SA="gke-node-sa@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in roles/logging.logWriter roles/monitoring.metricWriter \
            roles/monitoring.viewer roles/artifactregistry.reader \
            roles/stackdriver.resourceMetadata.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${NODE_SA}" --role="$ROLE" --condition=None
done
```

### 3.4 GKE cluster — 2 × e2-small, zonal

```bash
gcloud container clusters create heart-cluster \
  --zone="$ZONE" \
  --num-nodes=2 \
  --machine-type=e2-small \
  --disk-type=pd-standard \
  --disk-size=32 \
  --service-account="$NODE_SA" \
  --enable-ip-alias \
  --no-enable-managed-prometheus \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM \
  --workload-pool="${PROJECT_ID}.svc.id.goog" \
  --release-channel=regular
```

`--logging=SYSTEM,WORKLOAD` is what makes Deliverable 5 work: container stdout
is shipped to Cloud Logging automatically.

### 3.5 Workload Identity Federation for GitHub Actions (keyless)

```bash
gcloud iam service-accounts create gh-deployer --display-name="GitHub Actions deployer"
DEPLOY_SA="gh-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA}" --role=roles/artifactregistry.writer --condition=None
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA}" --role=roles/container.developer --condition=None

gcloud iam workload-identity-pools create github-pool \
  --location=global --display-name="GitHub Actions pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global --workload-identity-pool=github-pool \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository=='${GITHUB_OWNER}/${GITHUB_REPO}'"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
POOL_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"

echo "WIF_PROVIDER = ${POOL_ID}/providers/github-provider"
echo "WIF_SERVICE_ACCOUNT = ${DEPLOY_SA}"
```

`--attribute-condition` is not optional — without it, any repository on GitHub
could impersonate your service account, and recent `gcloud` versions refuse to
create the provider anyway.

### 3.6 Vertex AI Workbench instance (MLflow host)

```bash
gcloud workbench instances create mlops-workbench \
  --location="$ZONE" \
  --machine-type=e2-standard-2 \
  --metadata=idle-timeout-seconds=3600
```

Open it from **Vertex AI → Workbench → Instances → Open JupyterLab**.

### 3.7 Register the GitHub secrets and variables

`Settings → Secrets and variables → Actions`:

| Type | Name | Value |
|---|---|---|
| Secret | `WIF_PROVIDER` | `projects/<NUM>/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| Secret | `WIF_SERVICE_ACCOUNT` | `gh-deployer@<PROJECT_ID>.iam.gserviceaccount.com` |
| Variable | `GCP_PROJECT_ID` | your project id |
| Variable | `GCP_REGION` | `us-central1` |
| Variable | `GKE_ZONE` | `us-central1-a` |
| Variable | `GKE_CLUSTER` | `heart-cluster` |
| Variable | `AR_REPO` | `heart-repo` |

Or from Cloud Shell:

```bash
gh secret set WIF_PROVIDER      -b "${POOL_ID}/providers/github-provider"
gh secret set WIF_SERVICE_ACCOUNT -b "$DEPLOY_SA"
gh variable set GCP_PROJECT_ID -b "$PROJECT_ID"
gh variable set GCP_REGION     -b "$REGION"
gh variable set GKE_ZONE       -b "$ZONE"
gh variable set GKE_CLUSTER    -b "heart-cluster"
gh variable set AR_REPO        -b "heart-repo"
```

---

## Part 4 — Train, with MLflow on SQLite (in the Workbench)

Open a **Terminal** in JupyterLab:

```bash
git clone https://github.com/<GH_USER>/<ROLL>_IITMBS_MLOPS_OPPE2_MAY_2026.git
cd <ROLL>_IITMBS_MLOPS_OPPE2_MAY_2026

python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements-train.txt

python src/train.py
```

Expected output (numbers are reproducible with `seed=42`):

```
{ "accuracy": 0.847, "precision": 0.795, "recall": 0.969,
  "f1": 0.873, "roc_auc": 0.921, "cv_best_roc_auc": 0.898 }
saved: models/model.joblib
```

`src/train.py` writes the tracking DB to `mlflow/mlflow.db` (SQLite) and
artifacts to `mlruns/`. **View the MLflow UI:**

```bash
bash scripts/mlflow_ui.sh        # serves on 0.0.0.0:5000
```

From Cloud Shell, tunnel to it (do not open port 5000 to the internet):

```bash
gcloud compute ssh mlops-workbench --zone="$ZONE" --tunnel-through-iap -- -L 5000:localhost:5000
```

Then click **Web Preview → Change port → 5000** in Cloud Shell.
📸 *Screenshot the MLflow run page — params, metrics and the logged model.*

Commit the trained model so CI can bake it into the image:

```bash
git add models/model.joblib artifacts/ && git commit -m "trained model + metrics" && git push
```

---

## Part 5 — Deliverable 2: Explainability (SHAP) · 10 marks

```bash
python src/explain.py
```

Produces `artifacts/explainability_report.md`, `shap_beeswarm.png`,
`shap_bar.png`, `shap_feature_importance.csv`.

**Result (this is your answer to the question asked):**

| Rank (bottom) | Feature | Meaning | Share of total |
|---|---|---|---|
| 13 | `fbs` | fasting blood sugar > 120 mg/dl | 2.8% |
| 12 | `chol` | serum cholesterol | 2.9% |
| 11 | `trestbps` | resting blood pressure | 3.5% |
| 10 | `age` | age in years | 3.7% |

> **Plain English.** The factors with the *least* impact on the model's
> heart-disease prediction are **fasting blood sugar, serum cholesterol,
> resting blood pressure and age**. Together they account for under 13% of the
> model's explanatory weight. Two patients who differ only on these four
> measurements come out with almost the same risk score. The prediction is
> driven instead by chest-pain type, sex, exercise-induced angina, ST
> depression (`oldpeak`) and the number of vessels seen on fluoroscopy — i.e.
> by symptom and stress-test evidence rather than by baseline vitals.

The linear model makes this exact: SHAP is computed with `LinearExplainer` on
the scaled feature space, so the values are not an approximation.

---

## Part 6 — Deliverable 3: Fairness (Fairlearn) · 10 marks

```bash
python src/fairness.py --sensitive age gender
```

Age is continuous, so it is binned into clinical bands (`<=45`, `46-55`,
`56-65`, `>65`) — Fairlearn needs categorical groups. Gender is included too
because the pipeline overview mentions bias detection on gender.

**Result — bias is detected on both attributes:**

| Sensitive attribute | Demographic parity diff | DP ratio (80% rule) | Equalized odds diff | Verdict |
|---|---|---|---|---|
| `age` | 0.567 | 0.370 | 0.667 | **BIAS DETECTED** |
| `gender` | 0.248 | 0.702 | 0.127 | **BIAS DETECTED** |

> **Reading it.** For age, the `<=45` band gets a positive prediction 90% of
> the time while the `>65` band gets one only 33% of the time — a demographic
> parity difference of 0.567, far outside the ±0.10 band, and a parity ratio of
> 0.37 which fails the 80% rule badly. The false-positive rate tells the same
> story: 0.667 for under-45s versus 0.000 for over-65s, meaning the model
> systematically over-flags younger patients and under-flags the oldest group —
> the clinically dangerous direction. Gender shows a milder but still failing
> gap (parity ratio 0.702). Part of the age gap is real base-rate difference
> rather than model error, but the equalized-odds difference of 0.667 is a
> genuine error-rate disparity, not just a base-rate one.

Output: `artifacts/fairness_report.md`, `fairness_by_group_age.csv`,
`fairness_by_group_gender.csv`.

---

## Part 7 — Deliverable 4: Docker + GKE + CI/CD · 40 marks

Nothing to run manually — pushing to `main` triggers
`.github/workflows/cicd.yaml`, which:

1. **CI job** — installs deps, runs `pytest tests -q` (4 tests).
2. **CD job** — authenticates keylessly via WIF, builds `app/Dockerfile`,
   pushes `:<sha>` and `:latest` to Artifact Registry, fetches GKE credentials,
   substitutes the image into `k8s/deployment.yaml`, applies Deployment +
   Service + HPA, waits for rollout, then smoke-tests the live external IP.

```bash
git push origin main
gh run watch          # follow the workflow live
```

Verify on the cluster:

```bash
gcloud container clusters get-credentials heart-cluster --zone="$ZONE"

kubectl get deploy,pods,svc,hpa
kubectl describe hpa heart-api | head -20
```

You should see `maxReplicas: 3` on the HPA. Grab the external IP:

```bash
export API_IP=$(kubectl get svc heart-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "http://$API_IP"

curl -s "http://$API_IP/health"
curl -s -X POST "http://$API_IP/predict" -H 'Content-Type: application/json' \
  -d '{"age":63,"gender":"male","cp":3,"trestbps":145,"chol":233,"fbs":1,"restecg":0,
       "thalach":150,"exang":0,"oldpeak":2.3,"slope":0,"ca":0,"thal":1}'
```

Expected: `{"prediction":1,"label":"heart_disease","probability":0.582905,...}`

📸 *Screenshot: the green GitHub Actions run, `kubectl get pods,hpa`, and the
Artifact Registry image list.*

**API surface**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/ready` | readiness (model loaded) |
| GET | `/metrics` | request / prediction / error counters |
| POST | `/predict` | one patient |
| POST | `/predict_batch` | `{"instances": [...]}` |

---

## Part 8 — Deliverable 5: per-sample prediction + observability · 20 marks

Run from the **Workbench** (same region as the cluster, so latency is real):

```bash
python scripts/gen_sample.py                       # 100 random rows
python scripts/predict_loop.py --url "http://$API_IP"
```

Each row goes as its **own HTTP request**, so each prediction is an individual
log entry. You get two local audit files plus the server-side logs:

* `artifacts/prediction_log.jsonl` — one JSON object per request with
  `input_features`, `prediction`, `probability`, `timestamp`, `request_id`,
  `client_latency_ms`
* `artifacts/predictions_100.csv` — flat table for the report

Expected tail: `OK=100 ERR=0`.

**Observability in Cloud Logging.** The API writes structured JSON to stdout
with a `severity` key; GKE's agent parses it into `jsonPayload` automatically.
In the console go to **Logging → Logs Explorer** and paste:

```
resource.type="k8s_container"
resource.labels.cluster_name="heart-cluster"
resource.labels.container_name="heart-api"
jsonPayload.event="prediction"
```

Expand one entry — you will see the full `input_features` object, the
`prediction`, the `probability` and the `timestamp`.

Or pull them from the CLI:

```bash
bash scripts/fetch_logs.sh
```

📸 *Screenshot: Logs Explorer with an expanded prediction entry showing input
features + prediction + timestamp.*

---

## Part 9 — Deliverable 6: stress test with wrk · 10 marks

Install `wrk` on the Workbench:

```bash
sudo apt-get update && sudo apt-get install -y wrk

# if the package is unavailable:
sudo apt-get install -y build-essential libssl-dev git
git clone https://github.com/wg/wrk.git /tmp/wrk && make -C /tmp/wrk -j2
sudo cp /tmp/wrk/wrk /usr/local/bin/
```

Run it (`>2000` connections as required):

```bash
ulimit -n 65535
bash load/run_wrk.sh "http://$API_IP"
```

Defaults: **4 threads, 2100 connections, 60 s**, 10 s timeout, against
`POST /predict` with a real payload from `load/post.lua`. Override with
`CONN=3000 THREADS=8 DURATION=90s bash load/run_wrk.sh http://$API_IP`.

Report lands in `artifacts/wrk_report.txt`, and the script appends the HPA and
`kubectl top` state captured immediately after the run.

**What to write up.** Read three things off the wrk output:

* **Throughput** — `Requests/sec`. Expect roughly 400–1200 rps on 2 × e2-small
  with 3 pods; the exact number is yours to report.
* **Latency distribution** — the `--latency` block gives 50/75/90/99th
  percentiles. The p99 will be one to two orders of magnitude worse than p50
  once the connection count exceeds what 3 pods can serve; that gap is the
  story.
* **Timeouts / errors** — the `Socket errors` line (`connect`, `read`,
  `timeout`). With 2100 connections against a 3-pod ceiling you *should* see
  timeouts. That is the correct, expected result and the point of the exercise:
  the `maxReplicas: 3` cap means the service saturates, and beyond that point
  latency grows and requests time out rather than the system scaling further.

Watch autoscaling live in a second terminal during the run:

```bash
kubectl get hpa heart-api -w
kubectl get pods -l app=heart-api -w
```

📸 *Screenshot: the wrk output block, and `kubectl get hpa` showing replicas
climbing to 3.*

---

## Part 10 — Deliverable 7: input drift detection · 10 marks

```bash
python src/drift.py
```

Compares the **training distribution** (`artifacts/train_reference.csv`, the
234-row training split written by `src/train.py`) against the **100-row
generated dataset** used in Deliverable 5.

Three complementary tests:

* **Kolmogorov–Smirnov** two-sample test on the 5 continuous columns
* **Chi-square** on the 8 categorical columns (reference counts rescaled to the
  current sample size, so the test measures distribution *shape*, not sample size)
* **PSI** (Population Stability Index) on every column — `<0.10` stable,
  `0.10–0.25` moderate, `>0.25` major

**Result — 13/13 features drifted, verdict `SIGNIFICANT INPUT DRIFT`:**

| Feature | Test | p-value | PSI | Severity |
|---|---|---|---|---|
| `chol` | KS | <0.0001 | 2.451 | major |
| `trestbps` | KS | <0.0001 | 1.533 | major |
| `oldpeak` | KS | <0.0001 | 1.477 | major |
| `thal` | Chi² | <0.0001 | 1.169 | major |
| `ca` | Chi² | <0.0001 | 1.051 | major |
| `fbs` | Chi² | <0.0001 | 0.880 | major |
| … | | | | |
| `gender` | Chi² | 0.0057 | 0.070 | none (PSI) but significant |

> **Interpretation.** The prediction batch was generated by sampling each
> feature uniformly across its observed range rather than from the joint
> training distribution. Marginals are therefore flatter (mean cholesterol
> jumps from 246 to 347, mean `oldpeak` from 1.07 to 2.88) and the correlations
> that exist between real patients' attributes are gone entirely. A production
> monitor should fire on this: predictions from this batch are out-of-
> distribution and should be treated as low-confidence until the upstream data
> source is investigated. Note `gender` is a useful contrast — the chi-square
> flags it as statistically significant (p=0.006) while PSI calls it stable
> (0.07), which is the familiar disagreement between significance and effect
> size on a binary feature.

Output: `artifacts/drift_report.md`, `drift_report.csv`, `drift.json`.

---

## Part 11 — Commit your evidence

```bash
git add artifacts/ data/random_100.csv data/random_100.json
git commit -m "OPPE-2 evidence: SHAP, fairness, predictions, wrk, drift"
git push
```

**Checklist before you leave:**

- [ ] Repo private, named `<ROLL>_IITMBS_MLOPS_OPPE2_MAY_2026`
- [ ] `IITMBSMLOps` collaborator invite **accepted** (not pending)
- [ ] `artifacts/explainability_report.md` + SHAP plots — D2
- [ ] `artifacts/fairness_report.md` + per-group CSVs — D3
- [ ] Green GitHub Actions run; `kubectl get hpa` shows `maxReplicas 3` — D4
- [ ] `artifacts/prediction_log.jsonl` (100 lines) + Logs Explorer screenshot — D5
- [ ] `artifacts/wrk_report.txt` with >2000 connections — D6
- [ ] `artifacts/drift_report.md` — D7
- [ ] MLflow UI screenshot showing the tracked run

---

## Part 12 — Tear down (do this or you keep paying)

```bash
kubectl delete svc heart-api                       # releases the LoadBalancer first
gcloud container clusters delete heart-cluster --zone="$ZONE" --quiet
gcloud workbench instances delete mlops-workbench --location="$ZONE" --quiet
gcloud artifacts repositories delete heart-repo --location="$REGION" --quiet
```

Delete the Service *before* the cluster — otherwise the forwarding rule can be
orphaned and keeps billing.

---

## Part 13 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ValueError: invalid literal for int(): 'male'` | pandas ≥2.2 uses the `str` extension dtype, so `dtype == object` is False | already fixed — `src/preprocess.py` uses `pd.api.types.is_numeric_dtype` |
| `TypeError: Converting np.floating to a dtype not allowed` on `import shap` | shap ≤0.46 is incompatible with numpy ≥2.3 | `pip install -U "shap>=0.48"` (pinned in `requirements-train.txt`) |
| `kubectl apply` → `error converting YAML` | flow-style YAML containing `[` (e.g. `metadata.labels['app']`) | already fixed — manifests are block style |
| Pods `Pending`, `Insufficient cpu/memory` | 3 replicas won't fit the nodes | requests are already 150m/300Mi; if still stuck, `gcloud container clusters resize heart-cluster --num-nodes=3 --zone=$ZONE` |
| `InvalidImageName` / `IMAGE_PLACEHOLDER` | you applied the manifest by hand instead of via CI | `sed -i "s|IMAGE_PLACEHOLDER|$IMAGE:latest|g" k8s/deployment.yaml` first |
| HPA shows `<unknown>/60%` | metrics-server needs ~60 s after rollout, or CPU requests are missing | wait, then `kubectl describe hpa heart-api` |
| Actions: `Permission denied on IAM Service Account Credentials API` | `iamcredentials.googleapis.com` not enabled | enable it, re-run the workflow |
| Actions: `unable to acquire impersonated credentials` | `attribute-condition` repo string doesn't match | it must equal `owner/repo` exactly, case-sensitive |
| Actions: `denied: Permission artifactregistry.repositories.uploadArtifacts` | deployer SA missing role | `roles/artifactregistry.writer` on the project |
| `gke-gcloud-auth-plugin not found` | new GKE auth flow | `gcloud components install gke-gcloud-auth-plugin` (CI uses `get-gke-credentials@v2`, which handles it) |
| wrk: `too many open files` | fd limit below connection count | `ulimit -n 65535` before running; use `sudo` if refused |
| wrk shows 100% timeouts | LoadBalancer IP not ready, or you hit the pod ceiling | confirm `curl http://$API_IP/health` works first; then timeouts are the expected saturation result |
| Cloud Logging shows text, not `jsonPayload` | cluster created without workload logging | `gcloud container clusters update heart-cluster --zone=$ZONE --logging=SYSTEM,WORKLOAD` |
| `sklearn InconsistentVersionWarning` on model load | training env ≠ image env | both pin `scikit-learn==1.5.2`; re-train if you changed it |

---

## Appendix — folder structure

```
.
├── run.md                          # this file
├── README.md
├── requirements-train.txt          # Workbench / training deps
├── .gitignore  .dockerignore
├── data/
│   ├── data.csv                    # from MLOPS_MAY_2026_OPPE2
│   ├── random_100.csv              # D5 generated sample
│   └── random_100.json
├── src/
│   ├── preprocess.py               # shared schema — train / serve / drift
│   ├── train.py                    # D4 model + MLflow (SQLite)
│   ├── explain.py                  # D2 SHAP
│   ├── fairness.py                 # D3 Fairlearn
│   └── drift.py                    # D7 KS / Chi² / PSI
├── app/
│   ├── main.py                     # FastAPI + structured JSON logging
│   ├── requirements.txt            # runtime deps only (small image)
│   └── Dockerfile
├── k8s/
│   ├── deployment.yaml             # probes, resource requests, non-root
│   ├── service.yaml                # LoadBalancer :80 → :8080
│   └── hpa.yaml                    # min 1, MAX 3 pods, 60% CPU
├── .github/workflows/cicd.yaml     # D4 CI/CD via WIF
├── scripts/
│   ├── gen_sample.py               # D5 100 random rows
│   ├── predict_loop.py             # D5 per-sample requests + JSONL log
│   ├── fetch_logs.sh               # D5 pull logs from Cloud Logging
│   └── mlflow_ui.sh                # MLflow UI on SQLite
├── load/
│   ├── post.lua                    # D6 wrk POST body
│   └── run_wrk.sh                  # D6 2100 connections
├── tests/test_api.py               # CI gate
├── infra/
│   ├── config.sh                   # the 5 values you edit
│   └── setup.sh                    # one-shot GCP provisioning
├── models/model.joblib             # 2.4 KB, committed for the image build
└── artifacts/                      # all generated evidence
```
