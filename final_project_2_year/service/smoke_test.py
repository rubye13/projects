"""Проверка поднятого сервиса: нормальные и заведомо кривые запросы.

    python service/smoke_test.py --url http://localhost:8000

Нужна только стандартная библиотека, так что запускается где угодно.
Код выхода 0 - все проверки прошли.
"""

import argparse
import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

WARM_USER = 172  # есть история, шесть товаров-кандидатов
COLD_USER = 5  # в последние 8 недель не заходил, получает популярное


def call(base, method, path, body=None, raw=None, content_type="application/json"):
    data = (
        raw
        if raw is not None
        else (json.dumps(body).encode() if body is not None else None)
    )
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return (
                resp.status,
                resp.read().decode(),
                resp.headers.get("Content-Type", ""),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(), exc.headers.get("Content-Type", "")


def call_oversized(base, size=2 * 1024 * 1024):
    """Заявляет тело в 2 МБ и не шлёт его: сервис должен отказать сразу по заголовку."""
    url = urllib.parse.urlsplit(base)
    conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=30)
    conn.putrequest("POST", "/recommend")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", str(size))
    conn.endheaders()
    resp = conn.getresponse()
    status, text = resp.status, resp.read().decode()
    conn.close()
    return status, text


def as_json(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    base = parser.parse_args().url.rstrip("/")

    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(
            ("OK   " if ok else "FAIL ") + name + (f"  ->  {detail}" if detail else "")
        )

    status, text, _ = call(base, "GET", "/health")
    check("GET /health", status == 200 and as_json(text)["status"] == "ok", text)

    status, text, _ = call(base, "GET", "/info")
    info = as_json(text) or {}
    check(
        "GET /info",
        status == 200
        and info.get("model") == "CatBoostClassifier"
        and info.get("max_k") == 10,
        f"serve_cut={info.get('serve_cut')}, max_k={info.get('max_k')}",
    )

    status, text, _ = call(base, "GET", f"/recommend?user_id={WARM_USER}")
    res = as_json(text) or {}
    check(
        "GET /recommend, пользователь с историей",
        status == 200
        and len(res.get("items", [])) == 3
        and res.get("source") != "popular",
        text,
    )

    status, text, _ = call(base, "GET", f"/recommend?user_id={COLD_USER}&k=5")
    res = as_json(text) or {}
    check(
        "GET /recommend, новый пользователь и k=5",
        status == 200
        and len(res.get("items", [])) == 5
        and res.get("source") == "popular",
        text,
    )

    status, text, _ = call(
        base,
        "POST",
        "/recommend",
        {"user_ids": [WARM_USER, COLD_USER, WARM_USER], "k": 3},
    )
    res = as_json(text) or {}
    check(
        "POST /recommend, список из трёх",
        status == 200
        and len(res.get("results", [])) == 3
        and res["results"][0]["items"] == res["results"][2]["items"],
        text[:200],
    )

    body = json.dumps({"user_id": WARM_USER}).encode()
    status, text, _ = call(
        base, "POST", "/recommend", raw=body, content_type="text/plain"
    )
    check("POST /recommend без заголовка JSON", status == 200, text[:120])

    bad_requests = [
        ("GET", "/recommend", None, None, "нет user_id"),
        ("GET", "/recommend?user_id=abc", None, None, "user_id не число"),
        ("GET", "/recommend?user_id=1.5", None, None, "дробный user_id"),
        ("GET", "/recommend?user_id=-7", None, None, "отрицательный user_id"),
        ("GET", "/recommend?user_id=", None, None, "пустой user_id"),
        ("GET", "/recommend?user_id=" + "9" * 40, None, None, "огромный user_id"),
        ("GET", "/recommend?user_id=1&k=0", None, None, "k=0"),
        ("GET", "/recommend?user_id=1&k=100", None, None, "k больше 10"),
        ("GET", "/recommend?user_id=1&foo=bar", None, None, "лишний параметр"),
        ("POST", "/recommend", None, b"{not json", "битый JSON"),
        ("POST", "/recommend", [1, 2], None, "JSON-список вместо объекта"),
        ("POST", "/recommend", {"user_ids": []}, None, "пустой список"),
        ("POST", "/recommend", {"user_ids": [1, "x"]}, None, "строка в списке"),
        ("POST", "/recommend", {"user_ids": [True]}, None, "bool вместо id"),
        ("POST", "/recommend", {"user_ids": list(range(1001))}, None, "больше 1000 id"),
        ("POST", "/recommend", {"user_id": 1, "user_ids": [2]}, None, "оба поля сразу"),
    ]
    for method, path, body, raw, name in bad_requests:
        status, text, ctype = call(base, method, path, body=body, raw=raw)
        res = as_json(text) or {}
        check(
            f"400 на кривой запрос: {name}",
            status == 400 and "error" in res and "json" in ctype,
            text[:120],
        )

    status, text, _ = call(base, "GET", "/nope")
    check(
        "404 на неизвестный адрес",
        status == 404 and "error" in (as_json(text) or {}),
        text,
    )
    status, text, _ = call(base, "DELETE", "/recommend")
    check(
        "405 на неподдерживаемый метод",
        status == 405 and "error" in (as_json(text) or {}),
        text,
    )
    status, text = call_oversized(base)
    check("413 на тело больше 1 МБ", status == 413, text[:120])

    status, text, _ = call(base, "GET", f"/recommend?user_id={WARM_USER}")
    check("после кривых запросов сервис отвечает", status == 200, text)

    status, text, ctype = call(base, "GET", "/metrics")
    check(
        "GET /metrics в формате Prometheus",
        status == 200
        and "recsys_requests_total" in text
        and ctype.startswith("text/plain"),
        f"{len(text.splitlines())} строк",
    )

    passed = sum(checks)
    print(f"\n{passed} из {len(checks)} проверок прошли")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
