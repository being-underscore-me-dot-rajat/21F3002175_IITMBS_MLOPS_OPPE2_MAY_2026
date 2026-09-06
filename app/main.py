"""Heart-disease prediction API (Deliverables 4 & 5).

Every request is logged as one JSON line on stdout. GKE's logging agent ships
stdout to Cloud Logging and parses `severity` + the remaining keys into
jsonPayload, so no extra client library or cost is involved.
"""
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Literal, Union

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

MODEL_PATH = os.getenv("MODEL_PATH", "/app/models/model.joblib")
SERVICE = os.getenv("K_SERVICE", "heart-api")
VERSION = os.getenv("APP_VERSION", "dev")

FEATURES = ["age", "gender", "cp", "trestbps", "chol", "fbs", "restecg",
            "thalach", "exang", "oldpeak", "slope", "ca", "thal"]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "service": SERVICE,
            "version": VERSION,
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        return json.dumps(payload, default=str)


_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(JsonFormatter())
log = logging.getLogger("heart-api")
log.setLevel(logging.INFO)
log.handlers = [_h]
log.propagate = False


def jlog(level: str, message: str, **fields) -> None:
    log.log(getattr(logging, level), message, extra={"extra_fields": fields})


class Patient(BaseModel):
    age: float = Field(..., ge=0, le=120)
    gender: Union[int, Literal["male", "female", "m", "f", "Male", "Female"]]
    cp: int = Field(..., ge=0, le=3)
    trestbps: float = Field(..., gt=0)
    chol: float = Field(..., ge=0)
    fbs: int = Field(..., ge=0, le=1)
    restecg: int = Field(..., ge=0, le=2)
    thalach: float = Field(..., gt=0)
    exang: int = Field(..., ge=0, le=1)
    oldpeak: float
    slope: int = Field(..., ge=0, le=2)
    ca: int = Field(..., ge=0, le=4)
    thal: int = Field(..., ge=0, le=3)

    @field_validator("gender", mode="before")
    @classmethod
    def norm_gender(cls, v):
        if isinstance(v, str):
            return {"male": 1, "m": 1, "female": 0, "f": 0}[v.strip().lower()]
        return int(v)


class BatchRequest(BaseModel):
    instances: List[Patient]


STATE = {"model": None, "ready": False, "requests": 0, "predictions": 0,
         "errors": 0, "latency_sum_ms": 0.0}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bundle = joblib.load(MODEL_PATH)
    STATE["model"] = bundle["model"] if isinstance(bundle, dict) else bundle
    STATE["ready"] = True
    jlog("INFO", "model_loaded", model_path=MODEL_PATH, features=FEATURES,
         run_id=bundle.get("run_id") if isinstance(bundle, dict) else None)
    yield
    STATE["ready"] = False


app = FastAPI(title="Heart Disease Prediction API", version=VERSION,
              lifespan=lifespan)


def _frame(rows: List[Patient]) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in rows])[FEATURES]


def _predict(df: pd.DataFrame):
    proba = STATE["model"].predict_proba(df)[:, 1]
    return (proba >= 0.5).astype(int), proba


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/ready")
def ready():
    code = 200 if STATE["ready"] else 503
    return JSONResponse({"ready": STATE["ready"]}, status_code=code)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    avg = (STATE["latency_sum_ms"] / STATE["requests"]) if STATE["requests"] else 0
    return (f"heart_api_requests_total {STATE['requests']}\n"
            f"heart_api_predictions_total {STATE['predictions']}\n"
            f"heart_api_errors_total {STATE['errors']}\n"
            f"heart_api_latency_ms_avg {avg:.3f}\n")


@app.post("/predict")
def predict(patient: Patient, request: Request):
    rid = request.headers.get("x-request-id", str(uuid.uuid4()))
    t0 = time.perf_counter()
    STATE["requests"] += 1
    try:
        df = _frame([patient])
        pred, proba = _predict(df)
        ms = (time.perf_counter() - t0) * 1000
        STATE["predictions"] += 1
        STATE["latency_sum_ms"] += ms
        out = {"request_id": rid,
               "prediction": int(pred[0]),
               "label": "heart_disease" if pred[0] == 1 else "no_heart_disease",
               "probability": round(float(proba[0]), 6),
               "latency_ms": round(ms, 3),
               "timestamp": datetime.now(timezone.utc).isoformat()}
        # Deliverable 5: per-sample log line with inputs, output and timestamp.
        jlog("INFO", "prediction", event="prediction", request_id=rid,
             input_features=patient.model_dump(), prediction=out["prediction"],
             label=out["label"], probability=out["probability"],
             latency_ms=out["latency_ms"])
        return out
    except Exception as exc:
        STATE["errors"] += 1
        jlog("ERROR", "prediction_failed", event="prediction_error",
             request_id=rid, error=str(exc))
        return JSONResponse({"request_id": rid, "error": str(exc)},
                            status_code=400)


@app.post("/predict_batch")
def predict_batch(body: BatchRequest, request: Request):
    rid = request.headers.get("x-request-id", str(uuid.uuid4()))
    t0 = time.perf_counter()
    STATE["requests"] += 1
    df = _frame(body.instances)
    pred, proba = _predict(df)
    ms = (time.perf_counter() - t0) * 1000
    STATE["predictions"] += len(pred)
    STATE["latency_sum_ms"] += ms
    results = []
    for i, (p, pr) in enumerate(zip(pred, proba)):
        row = {"index": i, "prediction": int(p), "probability": round(float(pr), 6)}
        results.append(row)
        jlog("INFO", "prediction", event="prediction", request_id=f"{rid}-{i}",
             input_features=df.iloc[i].to_dict(), prediction=int(p),
             probability=round(float(pr), 6))
    return {"request_id": rid, "count": len(results), "results": results,
            "latency_ms": round(ms, 3)}
