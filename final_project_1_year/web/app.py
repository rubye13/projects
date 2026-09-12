"""Веб-сервис: по характеристикам дома отдаёт оценку цены"""

from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import (
    CAT_COLS,
    CB_CAT_COLS,
    NUM_COLS,
    prepare_frame,
)

app = Flask(__name__)
BUNDLE = joblib.load(ROOT / "models" / "price_model.joblib")
KIND = BUNDLE.get("kind", "sklearn")
STATE_KEEP = set(BUNDLE["state_keep"])
CITY_KEEP = set(BUNDLE.get("city_keep", []))
ZIP_KEEP = set(BUNDLE.get("zip_keep", []))
SQFT_MEDIANS = BUNDLE.get("sqft_medians", {})
SQFT_FALLBACK = BUNDLE.get("sqft_fallback")


def _row_from_json(payload: dict) -> pd.DataFrame:
    cols = NUM_COLS + CB_CAT_COLS
    data = {col: payload.get(col) for col in cols}
    if data.get("zip_code") is None and payload.get("zipcode") is not None:
        data["zip_code"] = payload.get("zipcode")
    frame = pd.DataFrame([data])
    return prepare_frame(
        frame, STATE_KEEP, CITY_KEEP, ZIP_KEEP, SQFT_MEDIANS, SQFT_FALLBACK
    )


def _predict_price(frame: pd.DataFrame) -> float:
    if KIND == "catboost":
        log_price = float(
            BUNDLE["model"].predict(frame[NUM_COLS + CB_CAT_COLS])[0]
        )
    else:
        log_price = float(
            BUNDLE["pipeline"].predict(frame[NUM_COLS + CAT_COLS])[0]
        )
    return float(np.clip(np.expm1(log_price), 10_000, 5_000_000))


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "realty-price",
        "health": "/health",
        "predict": "POST /predict",
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": BUNDLE.get("model_name"), "kind": KIND})


@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(force=True) or {}
    frame = _row_from_json(payload)
    price = _predict_price(frame)
    listed = payload.get("listed_price")
    result = {"predicted_price": round(price, 2)}
    if listed is not None:
        listed_f = float(listed)
        result["listed_price"] = listed_f
        result["delta"] = round(listed_f - price, 2)
        result["undervalued"] = bool(listed_f < price)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
