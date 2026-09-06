# Heart Disease Prediction - MLOps OPPE-2

Production deployment of a heart-disease classifier: FastAPI + Docker + GKE
(autoscaled to a max of 3 pods) with GitHub Actions CI/CD, SHAP explainability,
Fairlearn fairness testing, Cloud Logging observability, `wrk` stress testing
and input-drift detection. Experiment tracking runs in the Vertex AI Workbench
instance on an MLflow SQLite backend.

**Full step-by-step instructions: [`run.md`](run.md)**

| Deliverable | Where |
|---|---|
| D2 Explainability (SHAP) | `src/explain.py` -> `artifacts/explainability_report.md` |
| D3 Fairness (Fairlearn) | `src/fairness.py` -> `artifacts/fairness_report.md` |
| D4 Docker + GKE + CI/CD | `app/`, `k8s/`, `.github/workflows/cicd.yaml` |
| D5 Per-sample logging | `scripts/gen_sample.py`, `scripts/predict_loop.py`, `scripts/fetch_logs.sh` |
| D6 Stress test (wrk) | `load/run_wrk.sh` -> `artifacts/wrk_report.txt` |
| D7 Input drift | `src/drift.py` -> `artifacts/drift_report.md` |
