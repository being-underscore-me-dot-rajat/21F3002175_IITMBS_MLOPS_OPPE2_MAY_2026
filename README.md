# Heart Disease Prediction — Production MLOps Deployment

**Roll number:** 21F3002175
**Assessment:** MLOps OPPE-2, May 2026
**GCP project:** `oppe2-507808` · region `us-central1` · zone `us-central1-a`

A dockerized, API-served heart disease classifier running on Google Kubernetes
Engine with end-to-end CI/CD, explainability, fairness testing, per-sample
observability, stress testing and input drift detection.

* **Full runbook:** [`run.md`](run.md) — every command, in order, with a
  troubleshooting table.
* **AI usage disclosure:** [`AI_USAGE_REPORT.md`](AI_USAGE_REPORT.md)

---

## Architecture

```
Vertex AI Workbench (e2-standard-2)
  ├─ training + MLflow (SQLite backend, local artifacts)
  ├─ SHAP / Fairlearn / drift analysis
  └─ wrk load generator ──┐
                          ▼
GitHub  ──push──▶  GitHub Actions  ──WIF (keyless)──▶  Artifact Registry
                        │                                    │
                        └──────── kubectl apply ─────────────▼
                                              GKE Standard zonal, 2 × e2-small
                                                ├─ Deployment (FastAPI, non-root)
                                                ├─ Service (LoadBalancer :80→:8080)
                                                └─ HPA (min 1, max 3, 60% CPU)
                                                        │
                                                stdout JSON → Cloud Logging
```

**Cost choices.** Zonal rather than regional cluster; `e2-small` nodes on
32 GB `pd-standard` disks; Managed Prometheus disabled; MLflow on SQLite inside
the Workbench instead of Cloud SQL + GCS; the 2.4 KB model committed to git so
the CI image build needs no registry pull or credentials.

**Security choices.** Keyless CI via Workload Identity Federation with an
`attribute-condition` scoping impersonation to this repository alone; a scoped
node service account instead of the default Compute Engine identity; container
runs non-root with all capabilities dropped.

---

## Results

### Model

Logistic regression with `RandomizedSearchCV` over `C`, `StandardScaler`
pipeline, stratified 80/20 split, `seed=42`.

| Metric | Value |
|---|---|
| Accuracy | 0.847 |
| Precision | 0.795 |
| Recall | 0.969 |
| F1 | 0.873 |
| ROC-AUC | 0.921 |
| CV best ROC-AUC | 0.898 |

Tracked in MLflow (`mlflow/mlflow.db`); metrics also in `artifacts/metrics.json`.

### D2 — Explainability (SHAP)

The factors with the **least** impact on the prediction are **fasting blood
sugar** (2.8% of total explanatory weight), **serum cholesterol** (2.9%),
**resting blood pressure** (3.5%) and **age** (3.7%) — together under 13%. Two
patients differing only on these four measurements receive almost the same risk
score. The prediction is instead driven by chest-pain type, sex,
exercise-induced angina, ST depression (`oldpeak`) and the number of vessels on
fluoroscopy — that is, by symptom and stress-test evidence rather than baseline
vitals. → `artifacts/explainability_report.md`

### D3 — Fairness (Fairlearn)

Bias detected on **both** attributes.

| Sensitive attribute | Demographic parity diff | DP ratio (80% rule) | Equalized odds diff | Verdict |
|---|---|---|---|---|
| `age` (binned) | 0.567 | 0.370 | 0.667 | **BIAS DETECTED** |
| `gender` | 0.248 | 0.702 | 0.127 | **BIAS DETECTED** |

The `≤45` band receives a positive prediction 90% of the time versus 33% for
the `>65` band. False-positive rates run 0.667 versus 0.000 across the same
groups — the model over-flags younger patients and under-flags the oldest, the
clinically dangerous direction. → `artifacts/fairness_report.md`

### D4 — Deployment

Image built and pushed to Artifact Registry by GitHub Actions, deployed to GKE
with an HPA capped at **3 pods**. Endpoints: `/health`, `/ready`, `/metrics`,
`/predict`, `/predict_batch`. CI gate runs 4 pytest tests before any deploy.

### D5 — Per-sample logging

100 randomly generated rows sent as 100 individual HTTP requests. Each is logged
server-side as one structured JSON line carrying input features, prediction,
probability, request ID and timestamp, shipped to Cloud Logging by the GKE agent.
Local audit trail in `artifacts/prediction_log.jsonl`.

Logs Explorer query:

```
resource.type="k8s_container"
resource.labels.cluster_name="heart-cluster"
resource.labels.container_name="heart-api"
jsonPayload.event="prediction"
```

### D6 — Stress test

`wrk` at 4 threads / **2100 connections** / 60s against `POST /predict`.
Throughput, latency percentiles and socket timeouts in
`artifacts/wrk_report.txt`, with HPA state captured immediately after the run.
Timeouts under this load are the expected result: the `maxReplicas: 3` ceiling
means the service saturates rather than scaling further.

### D7 — Input drift

Training split (234 rows) versus the 100-row prediction set, using KS tests on
continuous columns, Chi-square on categoricals and PSI throughout.
**13/13 features drifted — verdict `SIGNIFICANT INPUT DRIFT`.** Mean cholesterol
moves 246 → 347, `oldpeak` 1.07 → 2.88. → `artifacts/drift_report.md`

---

## Deliverable map

| # | Deliverable | Code | Evidence |
|---|---|---|---|
| 1 | Private repo + collaborator | — | repository settings |
| 2 | Explainability | `src/explain.py` | `artifacts/explainability_report.md`, `shap_*.png` |
| 3 | Fairness | `src/fairness.py` | `artifacts/fairness_report.md`, `fairness_by_group_*.csv` |
| 4 | Docker + GKE + CI/CD | `app/`, `k8s/`, `.github/workflows/cicd.yaml` | Actions run, `kubectl get hpa` |
| 5 | Per-sample logging | `scripts/gen_sample.py`, `scripts/predict_loop.py`, `scripts/fetch_logs.sh` | `artifacts/prediction_log.jsonl`, Logs Explorer |
| 6 | Stress test | `load/run_wrk.sh`, `load/post.lua` | `artifacts/wrk_report.txt` |
| 7 | Input drift | `src/drift.py` | `artifacts/drift_report.md` |

---

## Repository layout

```
├── run.md                       # step-by-step runbook
├── AI_USAGE_REPORT.md           # AI usage disclosure
├── requirements-train.txt       # Workbench / analysis dependencies
├── data/                        # source data + generated 100-row sample
├── src/                         # preprocess, train, explain, fairness, drift
├── app/                         # FastAPI service, Dockerfile, runtime deps
├── k8s/                         # deployment, service, HPA
├── .github/workflows/cicd.yaml  # CI/CD via Workload Identity Federation
├── scripts/                     # sample generation, prediction loop, logs, MLflow
├── load/                        # wrk harness
├── tests/                       # pytest suite (CI gate)
├── infra/                       # gcloud provisioning
├── models/model.joblib          # trained model, baked into the image
└── artifacts/                   # all generated evidence
```

---

## Quick start

```bash
# 1. provision GCP (Cloud Shell)
vim infra/config.sh              # set the five values
bash infra/setup.sh              # APIs, Artifact Registry, GKE, WIF, Workbench

# 2. train and analyse (Workbench)
pip install -r requirements-train.txt
python src/train.py && python src/explain.py && python src/fairness.py

# 3. deploy
git push origin main             # triggers CI/CD

# 4. evidence
export API_IP=$(kubectl get svc heart-api -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
python scripts/gen_sample.py && python scripts/predict_loop.py --url "http://$API_IP"
bash load/run_wrk.sh "http://$API_IP"
python src/drift.py
```

Full detail, including the troubleshooting table, is in [`run.md`](run.md).

> **Teardown.** Delete the Service before the cluster, or the forwarding rule is
> orphaned and keeps billing. See `run.md` Part 12.