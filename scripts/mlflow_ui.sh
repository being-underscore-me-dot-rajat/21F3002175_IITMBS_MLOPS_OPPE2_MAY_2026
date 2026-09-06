#!/usr/bin/env bash
# Start the MLflow UI inside the Workbench instance with a SQLite backend.
set -euo pipefail
mkdir -p mlflow/artifacts
exec mlflow ui \
  --backend-store-uri "sqlite:///$(pwd)/mlflow/mlflow.db" \
  --artifacts-destination "$(pwd)/mlruns" \
  --host 0.0.0.0 --port 5000
