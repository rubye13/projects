"""Flask-приложение: рекомендации трёх товаров для главной по id пользователя.

Эндпоинты:
    GET  /health     жив ли сервис
    GET  /info       что за модель загружена
    GET  /recommend  ?user_id=<int>&k=<1..10> - подборка для одного пользователя
    POST /recommend  {"user_ids": [...], "k": 3} - подборки для списка
    GET  /metrics    счётчики в формате Prometheus

Локально: python -m service.app (из папки проекта). В контейнере сервис
поднимает gunicorn, см. Dockerfile.
"""

import logging
import os
import re
import time
from pathlib import Path

from flask import Flask, Response, g, jsonify, request
from werkzeug.exceptions import HTTPException

from service.metrics import Metrics
from service.recommender import Recommender

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_K = 3
MAX_K = 10
MAX_BATCH = 1000
MAX_USER_ID = 2**63 - 1
INT_RE = re.compile(r"-?[0-9]+")
PROMETHEUS_TYPE = "text/plain; version=0.0.4; charset=utf-8"

log = logging.getLogger("recsys")


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_int(value, name, low, high):
    """Целое из query-параметра или JSON. bool и дробные числа не пропускаю."""
    if isinstance(value, bool) or value is None:
        raise ApiError(f"{name} должен быть целым числом")
    if isinstance(value, float):
        if not value.is_integer():
            raise ApiError(f"{name} должен быть целым числом")
        value = int(value)
    if isinstance(value, str):
        text = value.strip()
        if not INT_RE.fullmatch(text) or len(text) > 20:
            raise ApiError(f"{name} должен быть целым числом, получено {value[:50]!r}")
        value = int(text)
    if not isinstance(value, int):
        raise ApiError(f"{name} должен быть целым числом")
    if not low <= value <= high:
        raise ApiError(f"{name} должен быть от {low} до {high}")
    return value


def error(message, status):
    return jsonify({"error": message, "status": status}), status


def create_app(model_dir=None):
    model_dir = Path(model_dir or os.environ.get("MODEL_DIR", DEFAULT_MODEL_DIR))
    started = time.time()
    recommender = Recommender(model_dir)
    max_k = min(MAX_K, recommender.max_k)
    metrics = Metrics(
        static_labels={
            "model": recommender.meta["model"],
            "serve_cut": recommender.meta["serve_cut"],
            "built_at": recommender.meta["built_at"],
        },
        gauges={
            "recsys_users_with_history": (
                len(recommender.user_ids),
                "Пользователей с персональными кандидатами",
            ),
            "recsys_candidates": (
                len(recommender.candidates),
                "Пар пользователь-товар в памяти",
            ),
            "recsys_model_load_seconds": (
                round(time.time() - started, 2),
                "Сколько грузились артефакты",
            ),
        },
    )
    log.info("модель загружена из %s за %.1f c", model_dir, time.time() - started)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def count_request(response):
        rule = request.url_rule.rule if request.url_rule else "unknown"
        seconds = time.perf_counter() - g.get("started", time.perf_counter())
        metrics.observe_request(rule, request.method, response.status_code, seconds)
        return response

    @app.errorhandler(ApiError)
    def bad_request(exc):
        return error(exc.message, exc.status)

    @app.errorhandler(HTTPException)
    def http_error(exc):
        messages = {
            404: "нет такого адреса, см. GET /info и документацию",
            405: "метод не поддерживается для этого адреса",
            413: "слишком большое тело запроса, максимум 1 МБ",
        }
        return error(messages.get(exc.code, exc.description), exc.code)

    @app.errorhandler(Exception)
    def internal_error(exc):
        log.exception("ошибка при обработке запроса")
        return error("внутренняя ошибка сервиса", 500)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "serve_cut": recommender.meta["serve_cut"]})

    @app.get("/info")
    def info():
        return jsonify({**recommender.info(), "max_k": max_k})

    @app.get("/recommend")
    def recommend_one():
        unknown = set(request.args) - {"user_id", "k"}
        if unknown:
            raise ApiError(f"неизвестные параметры: {', '.join(sorted(unknown))}")
        if "user_id" not in request.args:
            raise ApiError("нужен параметр user_id, например /recommend?user_id=172")
        user_id = parse_int(request.args["user_id"], "user_id", 0, MAX_USER_ID)
        k = parse_int(request.args.get("k", DEFAULT_K), "k", 1, max_k)
        result = recommender.recommend(user_id, k)
        metrics.observe_recommendations([result])
        return jsonify({"k": k, **result})

    @app.post("/recommend")
    def recommend_many():
        body = request.get_json(force=True, silent=True)
        if not isinstance(body, dict):
            raise ApiError(
                'тело должно быть JSON-объектом, например {"user_ids": [1, 2], "k": 3}'
            )
        unknown = set(body) - {"user_ids", "user_id", "k"}
        if unknown:
            raise ApiError(f"неизвестные поля: {', '.join(sorted(unknown))}")
        if "user_ids" in body and "user_id" in body:
            raise ApiError("передайте либо user_id, либо user_ids")
        if "user_id" in body:
            raw_ids = [body["user_id"]]
        elif "user_ids" in body:
            raw_ids = body["user_ids"]
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ApiError("user_ids должен быть непустым списком")
            if len(raw_ids) > MAX_BATCH:
                raise ApiError(f"не больше {MAX_BATCH} пользователей за запрос")
        else:
            raise ApiError("нужно поле user_ids (список) или user_id")
        user_ids = [parse_int(u, "user_id", 0, MAX_USER_ID) for u in raw_ids]
        k = parse_int(body.get("k", DEFAULT_K), "k", 1, max_k)
        results = recommender.recommend_many(user_ids, k)
        metrics.observe_recommendations(results)
        return jsonify({"k": k, "results": results})

    @app.get("/metrics")
    def prometheus_metrics():
        return Response(metrics.render(), mimetype=PROMETHEUS_TYPE)

    return app


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    create_app().run(host="0.0.0.0", port=port)
