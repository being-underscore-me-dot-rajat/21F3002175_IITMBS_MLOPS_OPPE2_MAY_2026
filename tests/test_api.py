import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
os.environ.setdefault("MODEL_PATH", os.path.join(
    os.path.dirname(__file__), "..", "models", "model.joblib"))
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

SAMPLE = {"age": 63, "gender": "male", "cp": 3, "trestbps": 145, "chol": 233,
          "fbs": 1, "restecg": 0, "thalach": 150, "exang": 0, "oldpeak": 2.3,
          "slope": 0, "ca": 0, "thal": 1}


def test_health():
    with TestClient(main.app) as c:
        assert c.get("/health").json()["status"] == "ok"


def test_predict_shape():
    with TestClient(main.app) as c:
        b = c.post("/predict", json=SAMPLE).json()
        assert b["prediction"] in (0, 1)
        assert 0.0 <= b["probability"] <= 1.0


def test_rejects_bad_input():
    with TestClient(main.app) as c:
        assert c.post("/predict", json={**SAMPLE, "cp": 99}).status_code == 422


def test_batch():
    with TestClient(main.app) as c:
        b = c.post("/predict_batch", json={"instances": [SAMPLE, SAMPLE]}).json()
        assert b["count"] == 2
