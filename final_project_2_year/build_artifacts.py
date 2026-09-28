"""Собирает артефакты сервиса из сырых данных RetailRocket.

Запуск из папки проекта:
    python build_artifacts.py --raw data/raw --out models

Что делает:
- читает лог и свойства, считает срезы train/valid/test как в ноутбуке недели 2
- обучает CatBoost на train и печатает Precision@3 на valid и test для контроля
- переобучает ту же модель на всех шести срезах, это модель для сервиса
- строит кандидатов с факторами на конец лога для всех, у кого есть история
- сохраняет модель, кандидатов, запасной список популярного и описание в models/
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier, Pool

from recsys.data import load_catalog, load_events
from recsys.features import (
    CUTS,
    FEATURES,
    HIST_DAYS,
    build_candidates,
    build_fold,
    popular_items,
    purchases,
)
from recsys.metrics import precision_at_k, purchase_coverage
from recsys.model import (
    CAT_FEATURES,
    MAX_CANDIDATES,
    cap_candidates,
    feature_frame_dtypes,
    to_model_frame,
    top_k,
)

TARGET = "target_cart"
PARAMS = {"iterations": 590, "learning_rate": 0.03, "depth": 4, "random_seed": 42}
N_POPULAR = 20


def log(msg, start):
    print(f"[{time.time() - start:6.1f} c] {msg}", flush=True)


def fit(pairs):
    model = CatBoostClassifier(**PARAMS, verbose=0, allow_writing_files=False)
    model.fit(Pool(to_model_frame(pairs), pairs[TARGET], cat_features=CAT_FEATURES))
    return model


def evaluate(model, pairs, events):
    cut = pairs["cut"].iloc[0]
    bought = purchases(events, cut)
    fallback = popular_items(events, cut)
    recs = top_k(pairs, model.predict_proba(to_model_frame(pairs))[:, 1])
    return {
        "precision_at_3": round(precision_at_k(recs, bought, fallback), 4),
        "purchase_coverage": round(purchase_coverage(recs, bought, fallback), 4),
        "buyers": len(bought),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--raw", default="data/raw", help="папка с csv RetailRocket")
    parser.add_argument("--out", default="models", help="куда сложить артефакты")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()

    events = load_events(args.raw)
    catalog = load_catalog(args.raw)
    log(f"лог {len(events)} событий, свойства {len(catalog.prop_hist)} записей", start)

    folds = {
        split: cap_candidates(
            pd.concat(
                [build_fold(events, cut, catalog)[0] for cut in cuts], ignore_index=True
            )
        )
        for split, cuts in CUTS.items()
    }
    log("срезы: " + ", ".join(f"{s} {len(df)} пар" for s, df in folds.items()), start)

    control = fit(folds["train"])
    metrics = {
        split: evaluate(control, folds[split], events) for split in ["valid", "test"]
    }
    log(f"модель на train: {metrics}", start)

    model = fit(pd.concat(folds.values(), ignore_index=True))
    log("модель для сервиса обучена на всех срезах", start)

    serve_cut = events["dt"].max().ceil("h")
    candidates, _ = build_candidates(events, serve_cut, catalog)
    candidates = feature_frame_dtypes(cap_candidates(candidates))
    popular = popular_items(events, serve_cut, n=N_POPULAR)
    log(
        f"срез сервиса {serve_cut}: {candidates['visitorid'].nunique()} пользователей, "
        f"{len(candidates)} кандидатов",
        start,
    )

    model.save_model(out / "ranker.cbm")
    candidates.to_parquet(out / "candidates.parquet", index=False)
    meta = {
        "model": "CatBoostClassifier",
        "params": PARAMS,
        "target": TARGET,
        "features": FEATURES,
        "cat_features": CAT_FEATURES,
        "max_candidates_per_user": MAX_CANDIDATES,
        "history_days": HIST_DAYS,
        "train_cuts": [str(c.date()) for cuts in CUTS.values() for c in cuts],
        "serve_cut": str(serve_cut),
        "users_with_history": int(candidates["visitorid"].nunique()),
        "candidates": len(candidates),
        "popular": [int(i) for i in popular],
        "metrics_model_trained_on_train": metrics,
        "built_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    log(f"готово: {sorted(p.name for p in out.iterdir())}", start)


if __name__ == "__main__":
    main()
