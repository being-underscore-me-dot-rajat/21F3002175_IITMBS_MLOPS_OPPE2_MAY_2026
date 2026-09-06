#!/usr/bin/env bash
# One-shot provisioning. Run in Google Cloud Shell:  bash infra/setup.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
gcloud config set project "$PROJECT_ID"

echo "== 1/6 enable APIs =="
gcloud services enable \
  container.googleapis.com artifactregistry.googleapis.com \
  compute.googleapis.com notebooks.googleapis.com aiplatform.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com \
  logging.googleapis.com monitoring.googleapis.com cloudresourcemanager.googleapis.com

echo "== 2/6 Artifact Registry =="
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker --location="$REGION" \
  --description="Heart disease API images" || echo "exists, skipping"

echo "== 3/6 least-privilege node service account =="
gcloud iam service-accounts create "$SA_NODE" \
  --display-name="GKE node SA" || echo "exists, skipping"
NODE_SA="${SA_NODE}@${PROJECT_ID}.iam.gserviceaccount.com"
for ROLE in roles/logging.logWriter roles/monitoring.metricWriter \
            roles/monitoring.viewer roles/artifactregistry.reader \
            roles/stackdriver.resourceMetadata.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${NODE_SA}" --role="$ROLE" --condition=None --quiet >/dev/null
done

echo "== 4/6 GKE Standard zonal cluster: 2x e2-small =="
gcloud container clusters create "$CLUSTER" \
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
  --release-channel=regular \
  --quiet

echo "== 5/6 Workload Identity Federation for GitHub Actions (keyless) =="
gcloud iam service-accounts create "$SA_DEPLOY" \
  --display-name="GitHub Actions deployer" || echo "exists, skipping"
DEPLOY_SA="${SA_DEPLOY}@${PROJECT_ID}.iam.gserviceaccount.com"
for ROLE in roles/artifactregistry.writer roles/container.developer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${DEPLOY_SA}" --role="$ROLE" --condition=None --quiet >/dev/null
done

gcloud iam workload-identity-pools create "$POOL" \
  --location=global --display-name="GitHub Actions pool" || echo "exists, skipping"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global --workload-identity-pool="$POOL" \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository=='${GITHUB_OWNER}/${GITHUB_REPO}'" \
  || echo "exists, skipping"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
POOL_ID="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}"

# Only this one repository may impersonate the deployer SA.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}" \
  --quiet

echo "== 6/6 Vertex AI Workbench instance (MLflow host) =="
gcloud workbench instances create "$WORKBENCH" \
  --location="$ZONE" \
  --machine-type=e2-standard-2 \
  --metadata=idle-timeout-seconds=3600 \
  || echo "exists, skipping"

cat <<SUMMARY

=========== ADD THESE TO GITHUB ===========
Settings > Secrets and variables > Actions > Secrets:
  WIF_PROVIDER        = ${POOL_ID}/providers/${PROVIDER}
  WIF_SERVICE_ACCOUNT = ${DEPLOY_SA}

Settings > Secrets and variables > Actions > Variables:
  GCP_PROJECT_ID = ${PROJECT_ID}
  GCP_REGION     = ${REGION}
  GKE_ZONE       = ${ZONE}
  GKE_CLUSTER    = ${CLUSTER}
  AR_REPO        = ${AR_REPO}
===========================================
SUMMARY
