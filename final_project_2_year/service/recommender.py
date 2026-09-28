"""Загрузка артефактов и подбор товаров для пользователя.

Для пользователя с историей берутся его кандидаты (до 50 последних товаров
с посчитанными факторами), CatBoost ставит каждому вероятность корзины или
покупки, показываются k лучших. Если своих товаров меньше k или истории нет,
места добиваются самыми покупаемыми товарами за последние 8 недель.
"""

import json
import threading
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

from recsys.metrics import fill_with
from recsys.model import to_model_frame, top_k


class Recommender:
    def __init__(self, model_dir):
        model_dir = Path(model_dir)
        self.meta = json.loads((model_dir / "meta.json").read_text())
        self.model = CatBoostClassifier()
        self.model.load_model(str(model_dir / "ranker.cbm"))
        self.popular = [int(i) for i in self.meta["popular"]]

        candidates = pd.read_parquet(model_dir / "candidates.parquet")
        candidates = candidates.sort_values("visitorid", kind="stable")
        self.candidates = candidates.reset_index(drop=True)
        users = self.candidates["visitorid"].to_numpy()
        self.user_ids, self.starts = np.unique(users, return_index=True)
        self.ends = np.append(self.starts[1:], len(users))
        # CatBoost предсказывает быстро, а одновременный вызов из потоков
        # не гарантирован, поэтому под замком
        self._lock = threading.Lock()

    @property
    def max_k(self):
        return len(self.popular)

    def _positions(self, user_ids):
        user_ids = np.asarray(user_ids, dtype=np.int64)
        pos = np.searchsorted(self.user_ids, user_ids)
        pos = np.minimum(pos, len(self.user_ids) - 1)
        found = self.user_ids[pos] == user_ids
        return pos, found

    def _score(self, rows):
        with self._lock:
            return self.model.predict_proba(to_model_frame(rows), thread_count=1)[:, 1]

    def recommend_many(self, user_ids, k=3):
        """Рекомендации для списка пользователей одним вызовом модели."""
        unique_ids = list(dict.fromkeys(int(u) for u in user_ids))
        pos, found = self._positions(unique_ids)
        known = [(self.starts[p], self.ends[p]) for p, f in zip(pos, found) if f]
        personal = {}
        if known:
            idx = np.concatenate([np.arange(s, e) for s, e in known])
            rows = self.candidates.iloc[idx]
            personal = top_k(rows, self._score(rows), k)

        results = []
        for user_id in user_ids:
            own = personal.get(int(user_id), [])
            items = fill_with(own, self.popular, k)
            if len(own) >= k:
                source = "personal"
            elif own:
                source = "personal+popular"
            else:
                source = "popular"
            results.append(
                {
                    "user_id": int(user_id),
                    "items": [int(i) for i in items],
                    "source": source,
                    "personal_items": len(own),
                }
            )
        return results

    def recommend(self, user_id, k=3):
        return self.recommend_many([user_id], k)[0]

    def info(self):
        keys = [
            "model",
            "params",
            "target",
            "features",
            "cat_features",
            "history_days",
            "max_candidates_per_user",
            "serve_cut",
            "users_with_history",
            "candidates",
            "metrics_model_trained_on_train",
            "built_at",
        ]
        info = {key: self.meta.get(key) for key in keys}
        info["popular_fallback"] = self.popular[:3]
        return info
