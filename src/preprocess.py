"""Shared schema + cleaning. Single source of truth for train / serve / drift."""
import pandas as pd

RAW_DROP = ["sno"]
GENDER_MAP = {"male": 1, "female": 0, "m": 1, "f": 0}
TARGET_MAP = {"yes": 1, "no": 0}

FEATURES = ["age", "gender", "cp", "trestbps", "chol", "fbs", "restecg",
            "thalach", "exang", "oldpeak", "slope", "ca", "thal"]

CATEGORICAL = ["gender", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"]
NUMERIC = ["age", "trestbps", "chol", "thalach", "oldpeak"]

PLAIN_NAMES = {
    "age": "age in years",
    "gender": "biological sex",
    "cp": "chest pain type",
    "trestbps": "resting blood pressure",
    "chol": "serum cholesterol",
    "fbs": "fasting blood sugar > 120 mg/dl",
    "restecg": "resting ECG result",
    "thalach": "maximum heart rate achieved",
    "exang": "exercise-induced angina",
    "oldpeak": "ST depression induced by exercise",
    "slope": "slope of the peak exercise ST segment",
    "ca": "number of major vessels coloured by fluoroscopy",
    "thal": "thalassemia / blood-flow defect type",
}


def encode_gender(s: pd.Series) -> pd.Series:
    # NOTE: do not test `dtype == object` -- pandas >=2.2 may use the `str`
    # extension dtype for text columns and that comparison silently fails.
    if pd.api.types.is_numeric_dtype(s):
        return s.astype(int)
    return s.astype("string").str.strip().str.lower().map(GENDER_MAP)


def load_raw(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def clean(df: pd.DataFrame, with_target: bool = True) -> pd.DataFrame:
    df = df.copy()
    df = df.drop(columns=[c for c in RAW_DROP if c in df.columns])
    if "gender" in df.columns:
        df["gender"] = encode_gender(df["gender"])
    if with_target and "target" in df.columns:
        if not pd.api.types.is_numeric_dtype(df["target"]):
            df["target"] = (df["target"].astype("string").str.strip()
                            .str.lower().map(TARGET_MAP))
    df = df.dropna().reset_index(drop=True)
    for c in df.columns:
        if c in CATEGORICAL or c == "target":
            df[c] = df[c].astype(int)
        else:
            df[c] = df[c].astype(float)
    return df


def split_xy(df: pd.DataFrame):
    return df[FEATURES], df["target"]
