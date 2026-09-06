# AI Usage Report

**Student:** 21F3002175
**Assessment:** MLOps OPPE-2 — Heart Disease Prediction, May 2026
**Tool used:** Claude (Anthropic), via the chat interface
**Repository:** `21F3002175_IITMBS_MLOPS_OPPE2_MAY_2026`

---

## 1. Summary

An AI assistant was used as a pair-programming and debugging partner for this
assessment. It contributed the initial scaffolding for the repository, the
first draft of every script, the Kubernetes manifests, the CI/CD workflow and
the `gcloud` provisioning commands. All architectural decisions, all GCP
resources, all execution, and all verification of results were carried out by
me.

The working pattern was iterative rather than single-shot: the assistant
produced a draft, I ran it against the real environment, and failures were fed
back for correction. A meaningful share of the total effort was spent on that
correction loop, and it is documented honestly in Section 4 below — including
the cases where the assistant's first answer was wrong.

---

## 2. What the assistant was asked to do

1. Read the provided `MLOPS_MAY_2026_OPPE2` repository and derive the real data
   schema rather than assume the standard UCI column set. This mattered: the
   dataset uses `gender` with string values `male`/`female`, a string `target`
   of `yes`/`no`, and an index column `sno` — none of which match the usual
   Cleveland layout.
2. Optimise for low cost and short wall-clock time without weakening any
   deliverable.
3. Use current Google documentation for all `gcloud` commands rather than
   recalled syntax.
4. Test every script before handing it over, and return corrected files rather
   than diffs when errors were found.

Before generating anything, the assistant asked which GKE flavour to target,
which CI authentication method to use, and what already existed in the project.
I chose GKE Standard zonal on 2 × `e2-small`, Workload Identity Federation, and
a from-scratch build.

---

## 3. What the assistant produced

| Area | Contribution |
|---|---|
| `src/preprocess.py` | Shared schema module so training, serving and drift detection cannot disagree about encoding |
| `src/train.py` | LogisticRegression + RandomizedSearchCV, MLflow tracking on a SQLite backend |
| `src/explain.py` | SHAP `LinearExplainer`, plain-English ranking of least-important features (D2) |
| `src/fairness.py` | Fairlearn `MetricFrame`, age binned into clinical bands, gender reported alongside (D3) |
| `src/drift.py` | KS test, Chi-square and PSI across all 13 features (D7) |
| `app/main.py` | FastAPI service with structured JSON logging to stdout for Cloud Logging pickup |
| `app/Dockerfile` | Slim, non-root runtime image |
| `k8s/` | Deployment with probes and resource requests, LoadBalancer Service, HPA capped at 3 pods (D4) |
| `.github/workflows/cicd.yaml` | Keyless CI/CD via Workload Identity Federation (D4) |
| `scripts/`, `load/` | 100-row generator, per-sample prediction client, log retrieval, `wrk` harness (D5, D6) |
| `infra/` | One-shot `gcloud` provisioning script |
| `run.md` | Step-by-step runbook with a troubleshooting table |

### Verification performed by the assistant before handover

The assistant executed the full pipeline in its own sandbox: training, SHAP,
Fairlearn, the 4-test pytest suite, the API under a live server, a 100-request
prediction loop, and drift detection. All YAML was parsed and all shell scripts
syntax-checked. Current `gcloud` syntax for Workload Identity Federation and
`gcloud workbench instances create` was verified against Google Cloud
documentation rather than recalled.

---

## 4. Errors, and who caught them

This section is the honest part. Three classes of error occurred.

### 4a. Caught by the assistant before I ever ran the code

| Error | Cause |
|---|---|
| `ValueError: invalid literal for int(): 'male'` | `dtype == object` is False under pandas ≥2.2, which uses a `str` extension dtype |
| `TypeError: Converting np.floating to a dtype not allowed` | `shap ≤0.46` is incompatible with `numpy ≥2.3`; resolved by pinning `shap>=0.48` |
| `kubectl apply` YAML parse failure | `metadata.labels['app']` inside flow-style YAML — the `[` breaks the parser |

### 4b. Errors in the assistant's own output, surfaced only when I ran it

| Error | Root cause |
|---|---|
| CI failed: `ModuleNotFoundError: No module named 'httpx'` | The assistant installed `httpx` manually in its sandbox and never added it to any requirements file. Fixed by adding it to the CI install step only, keeping the runtime image slim |
| `predict_loop.py` printed 100 lines of `None` instead of the actual error | Poor error surfacing in the assistant's script; patched to print the exception and fail fast on a malformed URL |
| MLflow instructions were needlessly complex | The assistant's first answer used an IAP SSH tunnel. I pointed out that the Workbench proxy works directly. On checking, MLflow 2.17 uses fully relative asset paths, so `/proxy/5000/` works with no flags — the tunnel was unnecessary |

### 4c. A wrong hypothesis the assistant corrected itself on

When four `artifacts/` files showed as modified in `git status`, the assistant
first proposed that SHAP's background subsampling was non-deterministic. It
then tested that claim directly, found the values identical across three runs,
and retracted the explanation. The real cause was that the delivered bundle
shipped with pre-generated artifacts which I had committed before regenerating
them locally.

### 4d. Environment problems the assistant diagnosed from my error output

| Symptom | Actual cause |
|---|---|
| `git status` showed `.venv/` as untracked despite a `.gitignore` rule | `cp -r source/* dest/` does not match dotfiles, so `.gitignore`, `.dockerignore` and — critically — `.github/workflows/` were never copied into the repository. Without the workflow file there would have been no CI/CD at all |
| `Invalid URL 'http:/predict': No host supplied` on all 100 samples | `$API_IP` was unset in the Workbench shell, since it had been exported in Cloud Shell |
| `403 Required "container.clusters.get" permission` | The Workbench VM runs as the Compute Engine default service account, which lacks cluster access in this project. Resolved by granting `roles/container.viewer` and `roles/logging.viewer` |

---

## 5. What I did without AI assistance

* Created and configured the GCP project, billing, and all resources.
* Created the private repository and managed collaborator access.
* Executed every command; the assistant had no access to my environment.
* Ran the training, explainability, fairness, prediction, stress-test and drift
  workloads and captured the evidence.
* Read every result and wrote the interpretations that appear in the reports.
* Diagnosed environment-specific issues by reading GCP console output.
* Made the cost/architecture trade-offs the assistant presented as options.

---

## 6. Assessment of the collaboration

**Where it helped most.** Boilerplate that is tedious but unforgiving —
Kubernetes manifests, the WIF trust chain, Dockerfile layering. Also catching
version-compatibility failures ahead of time; the `shap`/`numpy` incompatibility
in particular would have been an opaque stack trace to debug under time
pressure.

**Where it needed supervision.** It could not verify anything inside my GCP
project, so every claim about live infrastructure had to be checked by me. It
missed a test-only dependency because its sandbox had it installed already —
a reminder that "it worked on my machine" applies to AI sandboxes too. Its first
answer was sometimes over-engineered (the SSH tunnel) and sometimes confidently
wrong (the SHAP hypothesis); in both cases pushing back produced the correct
answer.

**Overall.** The assistant accelerated construction substantially and improved
the engineering quality of the result — the shared preprocessing module, the
non-root container, the scoped node service account and the attribute-condition
on the WIF provider are all better practice than I would have reached for
unaided. It did not remove the need to understand the system: every failure
after handover required me to read the error, locate the cause, and judge
whether the proposed fix was right.

---

*Prepared in accordance with the course's AI-usage disclosure expectations.*