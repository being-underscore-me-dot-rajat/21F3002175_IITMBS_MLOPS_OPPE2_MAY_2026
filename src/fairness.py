"""Deliverable 3 -- Fairness testing with Fairlearn.

Primary sensitive attribute is AGE (binned into clinical bands); gender is also
reported because the problem statement mentions bias detection on gender.

    python src/fairness.py --sensitive age
"""
import argparse
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from fairlearn.metrics import (MetricFrame, count,
                               demographic_parity_difference,
                               demographic_parity_ratio,
                               equalized_odds_difference,
                               false_positive_rate, selection_rate,
                               true_positive_rate)
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preprocess import FEATURES, clean, load_raw, split_xy  # noqa: E402

SEED = 42
AGE_BINS = [0, 45, 55, 65, 200]
AGE_LABELS = ["<=45", "46-55", "56-65", ">65"]


def sensitive_series(X: pd.DataFrame, name: str) -> pd.Series:
    if name == "age":
        return pd.cut(X["age"], bins=AGE_BINS, labels=AGE_LABELS).astype(str)
    if name == "gender":
        return X["gender"].map({1: "male", 0: "female"}).astype(str)
    return X[name].astype(str)


def analyse(y_true, y_pred, sf, name, out_dir):
    mf = MetricFrame(
        metrics={"count": count, "accuracy": accuracy_score,
                 "precision": precision_score, "recall_TPR": recall_score,
                 "selection_rate": selection_rate,
                 "true_positive_rate": true_positive_rate,
                 "false_positive_rate": false_positive_rate},
        y_true=y_true, y_pred=y_pred, sensitive_features=sf)

    by_group = mf.by_group.reset_index().rename(columns={"index": name})
    dpd = demographic_parity_difference(y_true, y_pred, sensitive_features=sf)
    dpr = demographic_parity_ratio(y_true, y_pred, sensitive_features=sf)
    eod = equalized_odds_difference(y_true, y_pred, sensitive_features=sf)
    acc_gap = float(mf.difference()["accuracy"])

    verdict = ("PASS" if (dpd <= 0.10 and dpr >= 0.80 and eod <= 0.10)
               else "BIAS DETECTED")
    summary = {"sensitive_attribute": name, "overall": {
        k: float(v) for k, v in mf.overall.items()},
        "demographic_parity_difference": float(dpd),
        "demographic_parity_ratio": float(dpr),
        "equalized_odds_difference": float(eod),
        "accuracy_gap": acc_gap, "verdict": verdict}

    md = [f"### Sensitive attribute: `{name}`", "",
          by_group.to_markdown(index=False, floatfmt=".3f"), "",
          f"- Demographic parity difference: **{dpd:.3f}** (fair if <= 0.10)",
          f"- Demographic parity ratio: **{dpr:.3f}** (fair if >= 0.80, the 80% rule)",
          f"- Equalized odds difference: **{eod:.3f}** (fair if <= 0.10)",
          f"- Largest accuracy gap between groups: **{acc_gap:.3f}**",
          f"- **Verdict: {verdict}**", ""]
    by_group.to_csv(f"{out_dir}/fairness_by_group_{name}.csv", index=False)
    return summary, "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/data.csv")
    ap.add_argument("--model", default="models/model.joblib")
    ap.add_argument("--out", default="artifacts")
    ap.add_argument("--sensitive", nargs="+", default=["age", "gender"])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    model = joblib.load(args.model)["model"]
    X, y = split_xy(clean(load_raw(args.data)))
    # Evaluate fairness on the held-out split (same seed/stratify as train.py).
    _, X_test, _, y_test = train_test_split(
        X[FEATURES], y, test_size=0.2, random_state=SEED, stratify=y)
    y_pred = model.predict(X_test)

    summaries, blocks = [], []
    for name in args.sensitive:
        s, md = analyse(y_test, y_pred, sensitive_series(X_test, name),
                        name, args.out)
        summaries.append(s); blocks.append(md)

    header = ["# Deliverable 3 - Fairness Testing with Fairlearn", "",
              "Metrics computed on the held-out test split. Age is binned into "
              "clinical bands because Fairlearn needs categorical groups.", ""]
    md = "\n".join(header + blocks)
    open(f"{args.out}/fairness_report.md", "w").write(md)
    json.dump(summaries, open(f"{args.out}/fairness.json", "w"), indent=2)
    print(md)


if __name__ == "__main__":
    main()
