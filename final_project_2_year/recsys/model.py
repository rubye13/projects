"""Подготовка кандидатов для CatBoost и выбор top-k. Общее для обучения и сервиса."""

from recsys.features import FEATURES

CAT_FEATURES = ["i_category", "i_root"]
MAX_CANDIDATES = 50


def cap_candidates(pairs, k=MAX_CANDIDATES):
    """Оставляет k самых свежих товаров на пользователя.

    У ботов и перекупщиков в истории тысячи товаров, на главной им всё равно
    показываются три. Ограничение убирает их перекос в обучении и экономит
    память сервиса.
    """
    group = ["cut", "visitorid"] if "cut" in pairs else ["visitorid"]
    ordered = pairs.sort_values(group + ["ui_days_since_last", "itemid"], kind="stable")
    return ordered.groupby(group).head(k).reset_index(drop=True)


def to_model_frame(pairs):
    """Факторы в том виде, в котором их ждёт модель: id категорий строками."""
    frame = pairs[FEATURES].copy()
    for col in CAT_FEATURES:
        frame[col] = frame[col].fillna(-1).astype(int).astype(str)
    return frame


def top_k(pairs, scores, k=3):
    """Для каждого пользователя k товаров с наибольшим скором."""
    ranked = pairs[["visitorid", "itemid"]].assign(score=scores)
    ranked = ranked.sort_values(
        ["visitorid", "score", "itemid"], ascending=[True, False, True], kind="stable"
    )
    ranked = ranked.groupby("visitorid").head(k)
    return ranked.groupby("visitorid")["itemid"].agg(list).to_dict()


def feature_frame_dtypes(pairs):
    """Компактные типы для хранения кандидатов в сервисе."""
    out = pairs[["visitorid", "itemid"] + FEATURES].copy()
    floats = [c for c in FEATURES if c not in CAT_FEATURES]
    out[floats] = out[floats].astype("float32")
    out[CAT_FEATURES] = out[CAT_FEATURES].astype("float32")
    out[["visitorid", "itemid"]] = out[["visitorid", "itemid"]].astype("int64")
    return out.reset_index(drop=True)
