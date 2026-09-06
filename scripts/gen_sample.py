"""Deliverable 5 (part 1) -- generate the 100-row random dataset.

Values are drawn uniformly across each column's observed range (numeric) or
from the observed categories (categorical). That is deliberately NOT the
training distribution, which is what makes Deliverable 7 interesting.
"""
import argparse, json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from preprocess import CATEGORICAL, FEATURES, NUMERIC, clean, load_raw  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/data.csv")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out-csv", default="data/random_100.csv")
    ap.add_argument("--out-json", default="data/random_100.json")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    ref = clean(load_raw(args.data))[FEATURES]
    rows = {}
    for c in FEATURES:
        if c in NUMERIC:
            lo, hi = float(ref[c].min()), float(ref[c].max())
            v = rng.uniform(lo, hi, args.n)
            rows[c] = np.round(v, 1) if c == "oldpeak" else np.round(v, 0)
        else:
            rows[c] = rng.choice(sorted(ref[c].unique()), args.n)
    df = pd.DataFrame(rows)[FEATURES]
    df["age"] = df["age"].astype(int)
    for c in CATEGORICAL:
        df[c] = df[c].astype(int)

    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    json.dump(df.to_dict("records"), open(args.out_json, "w"), indent=2)
    print(f"wrote {len(df)} rows -> {args.out_csv}, {args.out_json}")
    print(df.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
