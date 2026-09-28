"""Счётчики сервиса в текстовом формате Prometheus.

Без внешних библиотек: сервис работает одним процессом с несколькими потоками,
поэтому хватает словарей под замком.
"""

import threading
import time
from collections import defaultdict

LATENCY_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
SOURCES = ["personal", "personal+popular", "popular"]


def sample(name, value, **labels):
    """Одна строка метрики: name{label="value",...} value."""
    if not labels:
        return f"{name} {value}"
    pairs = ",".join(f'{key}="{val}"' for key, val in labels.items())
    return f"{name}{{{pairs}}} {value}"


class Metrics:
    def __init__(self, static_labels=None, gauges=None):
        self._lock = threading.Lock()
        self.started = time.time()
        self.static_labels = static_labels or {}
        self.gauges = gauges or {}
        self.requests = defaultdict(int)
        self.latency_sum = defaultdict(float)
        self.latency_count = defaultdict(int)
        self.latency_buckets = defaultdict(lambda: [0] * len(LATENCY_BUCKETS))
        self.recommendations = defaultdict(int)
        self.users_served = 0

    def observe_request(self, endpoint, method, status, seconds):
        with self._lock:
            self.requests[(endpoint, method, str(status))] += 1
            self.latency_sum[endpoint] += seconds
            self.latency_count[endpoint] += 1
            buckets = self.latency_buckets[endpoint]
            for i, bound in enumerate(LATENCY_BUCKETS):
                if seconds <= bound:
                    buckets[i] += 1

    def observe_recommendations(self, results):
        with self._lock:
            for res in results:
                self.recommendations[res["source"]] += 1
            self.users_served += len(results)

    def render(self):
        lines = []

        def block(name, kind, help_text):
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {kind}")

        with self._lock:
            name = "recsys_requests_total"
            block(name, "counter", "HTTP-запросы по эндпоинту, методу и коду ответа")
            for (endpoint, method, status), value in sorted(self.requests.items()):
                lines.append(
                    sample(name, value, endpoint=endpoint, method=method, status=status)
                )

            name = "recsys_request_duration_seconds"
            block(name, "histogram", "Время ответа, секунды")
            for endpoint in sorted(self.latency_count):
                buckets = self.latency_buckets[endpoint]
                for bound, value in zip(LATENCY_BUCKETS, buckets):
                    lines.append(
                        sample(name + "_bucket", value, endpoint=endpoint, le=bound)
                    )
                count = self.latency_count[endpoint]
                total = f"{self.latency_sum[endpoint]:.6f}"
                lines.append(
                    sample(name + "_bucket", count, endpoint=endpoint, le="+Inf")
                )
                lines.append(sample(name + "_sum", total, endpoint=endpoint))
                lines.append(sample(name + "_count", count, endpoint=endpoint))

            name = "recsys_recommendations_total"
            block(
                name, "counter", "Выданные подборки по источнику: " + ", ".join(SOURCES)
            )
            for source in SOURCES:
                lines.append(sample(name, self.recommendations[source], source=source))

            name = "recsys_users_served_total"
            block(name, "counter", "Пользователей, для которых выдан ответ")
            lines.append(sample(name, self.users_served))

        block("recsys_uptime_seconds", "gauge", "Сколько секунд работает сервис")
        lines.append(
            sample("recsys_uptime_seconds", f"{time.time() - self.started:.1f}")
        )

        for name, (value, help_text) in self.gauges.items():
            block(name, "gauge", help_text)
            lines.append(sample(name, value))

        block(
            "recsys_model_info",
            "gauge",
            "Описание загруженной модели, значение всегда 1",
        )
        lines.append(sample("recsys_model_info", 1, **self.static_labels))
        return "\n".join(lines) + "\n"
