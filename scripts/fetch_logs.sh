#!/usr/bin/env bash
# Deliverable 5 -- pull the per-sample prediction logs back out of Cloud Logging.
set -euo pipefail
CLUSTER="${CLUSTER:-heart-cluster}"
LIMIT="${LIMIT:-120}"
mkdir -p artifacts

FILTER='resource.type="k8s_container"
resource.labels.cluster_name="'"$CLUSTER"'"
resource.labels.container_name="heart-api"
jsonPayload.event="prediction"'

echo "== count of prediction log entries in the last hour =="
gcloud logging read "$FILTER
timestamp>=\"$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)\"" \
  --limit="$LIMIT" --format=json > artifacts/cloud_logging_predictions.json
python3 -c "import json;d=json.load(open('artifacts/cloud_logging_predictions.json'));print(len(d),'entries saved')"

echo "== newest 5, flattened =="
gcloud logging read "$FILTER" --limit=5 \
  --format="table(timestamp, jsonPayload.request_id, jsonPayload.prediction, jsonPayload.probability, jsonPayload.input_features.age, jsonPayload.input_features.chol)"
