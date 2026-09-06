"""Deliverable 2 -- SHAP explainability.

Ranks every feature by mean |SHAP| and writes a plain-English statement about
the features that matter LEAST for predicting heart disease.

    python src/explain.py
"""
import argparse
import json
import os
import sys

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from preprocess import FEATURES, PLAIN_NAMES, clean, load_raw, split_xy  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/data.csv")
    ap.add_argument("--model", default="models/model.joblib")
    ap.add_argument("--out", default="artifacts")
    ap.add_argument("--bottom", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    bundle = joblib.load(args.model)
    pipe = bundle["model"]
    scaler, clf = pipe.named_steps["scaler"], pipe.named_steps["clf"]

    X, _ = split_xy(clean(load_raw(args.data)))
    X = X[FEATURES]
    # SHAP is computed in the model's own (scaled) space, then attributed back
    # to the original column names -- a linear explainer is exact here.
    Xs = pd.DataFrame(scaler.transform(X), columns=FEATURES)

    explainer = shap.LinearExplainer(clf, Xs)
    sv = explainer(Xs)
    vals = np.asarray(sv.values)
    if vals.ndim == 3:                      # (n, features, classes)
        vals = vals[:, :, -1]

    mean_abs = np.abs(vals).mean(axis=0)
    rank = (pd.DataFrame({"feature": FEATURES, "mean_abs_shap": mean_abs})
            .sort_values("mean_abs_shap", ascending=False)
            .reset_index(drop=True))
    rank["share_pct"] = 100 * rank.mean_abs_shap / rank.mean_abs_shap.sum()
    rank["plain_english"] = rank.feature.map(PLAIN_NAMES)

    shap.summary_plot(vals, Xs, feature_names=FEATURES, show=False)
    plt.tight_layout(); plt.savefig(f"{args.out}/shap_beeswarm.png", dpi=120); plt.close()
    shap.summary_plot(vals, Xs, feature_names=FEATURES, plot_type="bar", show=False)
    plt.tight_layout(); plt.savefig(f"{args.out}/shap_bar.png", dpi=120); plt.close()

    least = rank.tail(args.bottom).iloc[::-1]
    lines = [
        "# Deliverable 2 - Model Explainability (SHAP)", "",
        "## Full feature importance (mean |SHAP| over the training data)", "",
        rank.to_markdown(index=False, floatfmt=".4f"), "",
        f"## Plain English: the {args.bottom} factors with the LEAST impact", "",
    ]
    for _, r in least.iterrows():
        lines.append(
            f"- **{r.feature}** ({r.plain_english}) contributes only "
            f"{r.share_pct:.1f}% of the model's total explanatory weight "
            f"(mean |SHAP| = {r.mean_abs_shap:.4f}). Changing this value moves "
            f"the predicted probability of heart disease very little, so the "
            f"model treats it as close to irrelevant."
        )
    lines += ["", "**Summary.** " + (
        "The model's decision is driven almost entirely by the top features; "
        + ", ".join(f"`{r.feature}` ({r.plain_english})" for _, r in least.iterrows())
        + " have the smallest influence. In clinical terms, these measurements "
          "barely change the prediction: two patients who differ only on these "
          "attributes receive practically the same risk score.")]

    md = "\n".join(lines)
    open(f"{args.out}/explainability_report.md", "w").write(md)
    rank.to_csv(f"{args.out}/shap_feature_importance.csv", index=False)
    json.dump({"least_important": least.feature.tolist(),
               "ranking": rank.to_dict("records")},
              open(f"{args.out}/explainability.json", "w"), indent=2)
    print(md)


if __name__ == "__main__":
    main()
