"""Precision@k по покупателям недели."""

import numpy as np


def fill_with(recs, fallback, k=3):
    """Добивает список до k товаров запасным списком без повторов."""
    out = list(recs)[:k]
    for item in fallback:
        if len(out) >= k:
            break
        if item not in out:
            out.append(item)
    return out


def precision_at_k(recs, bought, fallback, k=3, users=None):
    """Средняя доля купленных среди k показанных.

    recs - персональные списки {пользователь: [товары]}, bought - покупки недели
    {пользователь: set(товаров)}. Считаю по всем покупателям: кому нечего
    показать персонально, тому показывается fallback.
    """
    users = list(bought) if users is None else list(users)
    if not users:
        return float("nan")
    hits = [
        len(set(fill_with(recs.get(u, []), fallback, k)) & bought.get(u, set())) / k
        for u in users
    ]
    return float(np.mean(hits))


def purchase_coverage(recs, bought, fallback, k=3):
    """Доля покупок недели, которые попали в показанные k товаров."""
    total = sum(len(items) for items in bought.values())
    hit = sum(
        len(set(fill_with(recs.get(u, []), fallback, k)) & items)
        for u, items in bought.items()
    )
    return hit / total if total else float("nan")
