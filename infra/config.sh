#!/usr/bin/env bash
# ---- EDIT THESE FIVE LINES, everything else is derived --------------------
export PROJECT_ID="REPLACE_ME"                    # e.g. mlops-oppe2-471203
export GITHUB_OWNER="REPLACE_ME"                  # your GitHub username
export ROLL_NUMBER="REPLACE_ME"                   # e.g. 21f1000500
export REGION="us-central1"                       # cheapest GKE region
export ZONE="us-central1-a"
# --------------------------------------------------------------------------
export GITHUB_REPO="${ROLL_NUMBER}_IITMBS_MLOPS_OPPE2_MAY_2026"
export CLUSTER="heart-cluster"
export AR_REPO="heart-repo"
export IMAGE_NAME="heart-api"
export WORKBENCH="mlops-workbench"
export SA_DEPLOY="gh-deployer"
export SA_NODE="gke-node-sa"
export POOL="github-pool"
export PROVIDER="github-provider"
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}"
