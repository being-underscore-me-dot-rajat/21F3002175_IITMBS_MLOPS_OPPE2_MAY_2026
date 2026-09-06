"""Deliverable 5 (part 2) -- per-sample predictions against the deployed API.

Sends the 100 rows ONE AT A TIME so each prediction is an individual logged
request, and writes a local JSONL audit trail alongside the server-side logs.

    python scripts/predict_loop.py --url http://EXTERNAL_IP
"""
import argparse, csv, json, time, uuid
from datetime import datetime, timezone

import requests


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="base URL, e.g. http://34.1.2.3")
    ap.add_argument("--csv", default="data/random_100.csv")
    ap.add_argument("--out", default="artifacts/prediction_log.jsonl")
    ap.add_argument("--results", default="artifacts/predictions_100.csv")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    endpoint = args.url.rstrip("/") + "/predict"
    sess = requests.Session()
    ok = err = 0
    logf = open(args.out, "w")
    resf = open(args.results, "w", newline="")
    writer = None

    for i, raw in enumerate(rows):
        payload = {k: (float(v) if k in ("oldpeak", "chol", "trestbps",
                                         "thalach", "age") else int(float(v)))
                   for k, v in raw.items()}
        rid = str(uuid.uuid4())
        t0 = time.perf_counter()
        try:
            r = sess.post(endpoint, json=payload, timeout=15,
                          headers={"x-request-id": rid})
            ms = (time.perf_counter() - t0) * 1000
            body = r.json()
            rec = {"sample_index": i, "request_id": rid,
                   "timestamp": datetime.now(timezone.utc).isoformat(),
                   "input_features": payload, "status_code": r.status_code,
                   "prediction": body.get("prediction"),
                   "label": body.get("label"),
                   "probability": body.get("probability"),
                   "client_latency_ms": round(ms, 2)}
            ok += r.status_code == 200
        except Exception as exc:
            err += 1
            rec = {"sample_index": i, "request_id": rid,
                   "timestamp": datetime.now(timezone.utc).isoformat(),
                   "input_features": payload, "error": str(exc)}
        logf.write(json.dumps(rec) + "\n")
        flat = {**payload, "prediction": rec.get("prediction"),
                "probability": rec.get("probability"),
                "timestamp": rec["timestamp"], "request_id": rid}
        if writer is None:
            writer = csv.DictWriter(resf, fieldnames=list(flat))
            writer.writeheader()
        writer.writerow(flat)
        print(f"[{i+1:3}/{len(rows)}] {rec.get('prediction')} "
              f"p={rec.get('probability')} {rec.get('client_latency_ms')}ms")

    logf.close(); resf.close()
    print(f"\nOK={ok} ERR={err} -> {args.out} , {args.results}")


if __name__ == "__main__":
    main()
