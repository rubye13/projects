"""Факторы для пар пользователь-товар на срезе.

Код перенесён из ноутбука недели 2 без изменений логики. Факторы считаются
по событиям за HIST_DAYS до среза, свойства товара берутся последним
значением строго до среза.
"""

import numpy as np
import pandas as pd

from recsys.data import EVENT_TYPES

HIST_DAYS = 56
TARGET_DAYS = 7
CUTS = {
    "train": pd.to_datetime(["2015-08-07", "2015-08-14", "2015-08-21", "2015-08-28"]),
    "valid": pd.to_datetime(["2015-09-04"]),
    "test": pd.to_datetime(["2015-09-11"]),
}
KEYS = ["visitorid", "itemid"]
TARGETS = ["target", "target_cart"]
FEATURES = [
    "ui_views",
    "ui_carts",
    "ui_trans",
    "ui_days_since_first",
    "ui_days_since_last",
    "ui_sessions",
    "ui_view_share",
    "uc_share",
    "ui_in_last_session",
    "u_views",
    "u_carts",
    "u_trans",
    "u_items",
    "u_sessions",
    "u_days",
    "u_days_since_first",
    "u_days_since_last",
    "u_cart_rate",
    "u_events_per_session",
    "i_views",
    "i_carts",
    "i_trans",
    "i_users",
    "i_days_since_first",
    "i_days_since_last",
    "i_views_7d",
    "i_trend",
    "i_cart_rate",
    "i_trans_rate",
    "i_category",
    "i_available",
    "i_price",
    "i_root",
    "i_depth",
    "c_views",
    "c_trans",
    "i_rank_in_cat",
]
FEATURE_DESC = {
    "ui_views": "сколько раз человек смотрел товар",
    "ui_carts": "сколько раз клал товар в корзину",
    "ui_trans": "сколько раз покупал товар",
    "ui_days_since_first": "дней с первого контакта с товаром",
    "ui_days_since_last": "дней с последнего контакта с товаром",
    "ui_sessions": "в скольких сессиях был товар",
    "ui_view_share": "доля товара в просмотрах человека",
    "uc_share": "доля событий человека в категории товара",
    "ui_in_last_session": "товар был в последней сессии, 0/1",
    "u_views": "просмотры пользователя",
    "u_carts": "корзины пользователя",
    "u_trans": "покупки пользователя",
    "u_items": "разных товаров у пользователя",
    "u_sessions": "сессий",
    "u_days": "дней с активностью",
    "u_days_since_first": "дней с первого события в окне",
    "u_days_since_last": "дней с последнего события",
    "u_cart_rate": "корзины на просмотр",
    "u_events_per_session": "событий на сессию",
    "i_views": "просмотры товара",
    "i_carts": "корзины товара",
    "i_trans": "покупки товара",
    "i_users": "уникальных посетителей товара",
    "i_days_since_first": "дней с первого события по товару",
    "i_days_since_last": "дней с последнего события по товару",
    "i_views_7d": "просмотры товара за последнюю неделю",
    "i_trend": "неделя к среднему недельному по окну",
    "i_cart_rate": "сглаженная конверсия в корзину",
    "i_trans_rate": "сглаженная конверсия в покупку",
    "i_category": "категория на момент среза, id",
    "i_available": "доступность на момент среза, 0/1",
    "i_price": "свойство 790 (цена) на момент среза",
    "i_root": "корневая категория, id",
    "i_depth": "глубина категории в дереве",
    "c_views": "просмотры всех товаров категории",
    "c_trans": "покупки в категории",
    "i_rank_in_cat": "место товара в категории по просмотрам",
}


def smooth_rate(pos, total, m=20):
    prior = pos.sum() / max(total.sum(), 1)
    return (pos + prior * m) / (total + m)


def last_value_before(prop_hist, prop, cut):
    part = prop_hist[(prop_hist["property"] == prop) & (prop_hist["dt"] < cut)]
    return part.groupby("itemid")["value"].last()


def count_events(df, keys, prefix):
    cnt = pd.crosstab([df[k] for k in keys], df["event"])
    cnt = cnt.reindex(columns=EVENT_TYPES, fill_value=0)
    cnt.columns = [prefix + "views", prefix + "carts", prefix + "trans"]
    return cnt


def history(events, cut):
    """События окна перед срезом и сколько дней прошло до среза."""
    start = cut - pd.Timedelta(days=HIST_DAYS)
    hist = events[(events["dt"] >= start) & (events["dt"] < cut)].copy()
    hist["days_ago"] = (cut - hist["dt"]).dt.total_seconds() / 86400
    return hist


def item_features(hist, cut, catalog):
    feats = count_events(hist, ["itemid"], "i_").join(
        hist.groupby("itemid").agg(
            i_users=("visitorid", "nunique"),
            i_days_since_first=("days_ago", "max"),
            i_days_since_last=("days_ago", "min"),
        )
    )
    week_views = hist[(hist["days_ago"] <= 7) & (hist["event"] == "view")]
    feats["i_views_7d"] = (
        week_views.groupby("itemid").size().reindex(feats.index, fill_value=0)
    )
    feats["i_trend"] = feats["i_views_7d"] / (feats["i_views"] / (HIST_DAYS / 7) + 1)
    feats["i_cart_rate"] = smooth_rate(feats["i_carts"], feats["i_views"])
    feats["i_trans_rate"] = smooth_rate(feats["i_trans"], feats["i_views"])

    for prop in ["category", "available", "price"]:
        values = last_value_before(catalog.prop_hist, prop, cut)
        feats["i_" + prop] = values.reindex(feats.index)
    feats["i_root"] = feats["i_category"].map(catalog.cat_root)
    feats["i_depth"] = feats["i_category"].map(catalog.cat_depth)

    cat_sum = feats.groupby("i_category")[["i_views", "i_trans"]].sum()
    feats["c_views"] = feats["i_category"].map(cat_sum["i_views"])
    feats["c_trans"] = feats["i_category"].map(cat_sum["i_trans"])
    feats["i_rank_in_cat"] = feats.groupby("i_category")["i_views"].rank(
        ascending=False, method="min"
    )
    return feats


def user_features(hist):
    feats = count_events(hist, ["visitorid"], "u_").join(
        hist.groupby("visitorid").agg(
            u_items=("itemid", "nunique"),
            u_sessions=("session", "nunique"),
            u_days=("day", "nunique"),
            u_days_since_first=("days_ago", "max"),
            u_days_since_last=("days_ago", "min"),
        )
    )
    n_events = feats[["u_views", "u_carts", "u_trans"]].sum(axis=1)
    feats["u_cart_rate"] = feats["u_carts"] / feats["u_views"].clip(lower=1)
    feats["u_events_per_session"] = n_events / feats["u_sessions"]
    return feats


def pair_features(hist, items):
    pairs = (
        count_events(hist, KEYS, "ui_")
        .join(
            hist.groupby(KEYS).agg(
                ui_days_since_first=("days_ago", "max"),
                ui_days_since_last=("days_ago", "min"),
                ui_sessions=("session", "nunique"),
            )
        )
        .reset_index()
    )

    u_views = hist[hist["event"] == "view"].groupby("visitorid").size()
    user_views = pairs["visitorid"].map(u_views).fillna(0).clip(lower=1)
    pairs["ui_view_share"] = pairs["ui_views"] / user_views

    hist_cat = hist.assign(category=hist["itemid"].map(items["i_category"]))
    uc = (
        hist_cat.groupby(["visitorid", "category"])
        .size()
        .rename("uc_events")
        .reset_index()
    )
    pairs["category"] = pairs["itemid"].map(items["i_category"])
    pairs = pairs.merge(uc, on=["visitorid", "category"], how="left")
    u_total = hist.groupby("visitorid").size()
    pairs["uc_share"] = pairs["uc_events"] / pairs["visitorid"].map(u_total)
    pairs.loc[pairs["category"].isna(), "uc_share"] = np.nan

    last_session = hist.groupby("visitorid")["session"].max()
    in_last = hist[hist["session"] == hist["visitorid"].map(last_session)]
    in_last = in_last[KEYS].drop_duplicates().assign(ui_in_last_session=1)
    pairs = pairs.merge(in_last, on=KEYS, how="left")
    pairs["ui_in_last_session"] = pairs["ui_in_last_session"].fillna(0).astype(int)
    return pairs.drop(columns=["category", "uc_events"])


def build_candidates(events, cut, catalog, users=None):
    """Кандидаты на срезе: все пары из истории пользователей с факторами.

    users - кого оставить (на обучении это активные в неделю таргета),
    None - всех, у кого есть история в окне. Так кандидаты строятся в сервисе.
    """
    hist = history(events, cut)
    items = item_features(hist, cut, catalog)
    if users is not None:
        hist = hist[hist["visitorid"].isin(users)]
    pairs = pair_features(hist, items)
    pairs = pairs.merge(user_features(hist), left_on="visitorid", right_index=True)
    pairs = pairs.merge(items, left_on="itemid", right_index=True)
    return pairs, items


def build_fold(events, cut, catalog):
    """Срез для обучения и проверки: кандидаты активных в неделю таргета и таргеты."""
    end = cut + pd.Timedelta(days=TARGET_DAYS)
    future = events[(events["dt"] >= cut) & (events["dt"] < end)]
    pairs, items = build_candidates(
        events, cut, catalog, users=future["visitorid"].unique()
    )

    bought = future.loc[future["event"] == "transaction", KEYS].drop_duplicates()
    carted = future.loc[future["event"] != "view", KEYS].drop_duplicates()
    pairs = pairs.merge(bought.assign(target=1), on=KEYS, how="left")
    pairs = pairs.merge(carted.assign(target_cart=1), on=KEYS, how="left")
    pairs[TARGETS] = pairs[TARGETS].fillna(0).astype(int)
    pairs["cut"] = cut
    return pairs, items


def purchases(events, cut):
    """Что купил каждый покупатель за неделю после среза."""
    end = cut + pd.Timedelta(days=TARGET_DAYS)
    week = events[(events["dt"] >= cut) & (events["dt"] < end)]
    bought = week[week["event"] == "transaction"]
    return bought.groupby("visitorid")["itemid"].agg(set).to_dict()


def popular_items(events, cut, n=3, days=HIST_DAYS):
    """Самые покупаемые товары за days дней до среза."""
    start = cut - pd.Timedelta(days=days)
    window = events[(events["dt"] >= start) & (events["dt"] < cut)]
    bought = window.loc[window["event"] == "transaction", "itemid"]
    return bought.value_counts().index[:n].tolist()
