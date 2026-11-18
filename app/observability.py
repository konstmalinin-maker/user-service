"""Метрики FastAPI через prometheus-flask-exporter и OpenTelemetry."""

import os
import time
from pathlib import Path

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from flask import Flask
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_flask_exporter import PrometheusMetrics
from starlette.middleware.wsgi import WSGIMiddleware


def configure_observability(app, service: str):
    registry = CollectorRegistry()
    requests = Counter(
        "api_requests_total", "Completed HTTP requests", ["service", "method", "route", "status"], registry=registry
    )
    latency = Histogram(
        "api_request_duration_seconds",
        "API latency",
        ["service", "route"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
        registry=registry,
    )
    breaker = Gauge("circuit_breaker_state", "0 closed, 0.5 half-open, 1 open", ["service"], registry=registry).labels(
        service
    )
    breaker.set(0)
    exporter = Flask(service + "-metrics")
    PrometheusMetrics(exporter, path="/", registry=registry)
    app.mount("/metrics", WSGIMiddleware(exporter))

    @app.middleware("http")
    async def record(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        if not request.url.path.startswith(("/metrics", "/static", "/docs", "/openapi.json")):
            route = getattr(request.scope.get("route"), "path", "unmatched")
            requests.labels(service, request.method, route, str(response.status_code)).inc()
            latency.labels(service, route).observe(time.perf_counter() - start)
        return response

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces"), schedule_delay_millis=500
            )
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(
            app, tracer_provider=provider, excluded_urls="health,metrics,docs,static,openapi.json"
        )
    return breaker


def local_swagger(app):
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/docs", include_in_schema=False)
    def docs():
        return get_swagger_ui_html(
            openapi_url="./openapi.json",
            title=app.title + " — Swagger",
            swagger_js_url="./static/swagger-ui-bundle.js",
            swagger_css_url="./static/swagger-ui.css",
            swagger_favicon_url="data:,",
        )
