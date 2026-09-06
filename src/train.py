"""Train the heart-disease classifier and track the run in MLflow (SQLite backend).

Run from repo root inside the Vertex AI Workbench instance:
    python src/train.py
"""
import argparse
import json
import os
import sys

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preprocess import FEATURES, clean, load_raw, split_xy  # noqa: E402

SEED = 42


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/data.csv")
    ap.add_argument("--model-out", default="models/model.joblib")
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--tracking-uri", default=os.getenv(
        "MLFLOW_TRACKING_URI", "sqlite:///mlflow/mlflow.db"))
    ap.add_argument("--experiment", default="heart-disease-oppe2")
    args = ap.parse_args()

    os.makedirs("mlflow/artifacts", exist_ok=True)
    os.makedirs(os.path.dirname(args.model_out) or ".", exist_ok=True)
    os.makedirs(args.artifacts, exist_ok=True)

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experiment)

    df = clean(load_raw(args.data))
    X, y = split_xy(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y)

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, random_state=SEED)),
    ])
    grid = {"clf__C": np.logspace(-4, 4, 20), "clf__solver": ["liblinear"]}
    search = RandomizedSearchCV(pipe, grid, n_iter=20, cv=5, scoring="roc_auc",
                                random_state=SEED, n_jobs=-1)

    with mlflow.start_run(run_name="logreg-randomsearch") as run:
        search.fit(X_train, y_train)
        model = search.best_estimator_

        proba = model.predict_proba(X_test)[:, 1]
        pred = (proba >= 0.5).astype(int)
        metrics = {
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred),
            "recall": recall_score(y_test, pred),
            "f1": f1_score(y_test, pred),
            "roc_auc": roc_auc_score(y_test, proba),
            "cv_best_roc_auc": search.best_score_,
        }

        mlflow.log_params({k: str(v) for k, v in search.best_params_.items()})
        mlflow.log_params({"n_rows_clean": len(df), "n_features": len(FEATURES),
                           "seed": SEED, "test_size": 0.2})
        mlflow.log_metrics(metrics)

        rep = classification_report(y_test, pred, digits=3)
        cm = confusion_matrix(y_test, pred).tolist()
        with open(f"{args.artifacts}/classification_report.txt", "w") as f:
            f.write(rep + f"\nconfusion_matrix={cm}\n")
        with open(f"{args.artifacts}/metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        mlflow.log_artifact(f"{args.artifacts}/classification_report.txt")
        mlflow.log_artifact(f"{args.artifacts}/metrics.json")

        # Reference stats for drift detection (Deliverable 7).
        X_train.assign(target=y_train.values).to_csv(
            f"{args.artifacts}/train_reference.csv", index=False)
        mlflow.log_artifact(f"{args.artifacts}/train_reference.csv")

        mlflow.sklearn.log_model(model, artifact_path="model")

        bundle = {"model": model, "features": FEATURES,
                  "run_id": run.info.run_id, "metrics": metrics}
        joblib.dump(bundle, args.model_out)
        print(json.dumps(metrics, indent=2))
        print("run_id:", run.info.run_id)
        print("saved:", args.model_out)


if __name__ == "__main__":
    main()
