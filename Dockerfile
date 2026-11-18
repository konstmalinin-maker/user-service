# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY requirements-runtime.txt .
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements-runtime.txt; else pip install --no-cache-dir -r requirements-runtime.txt; fi && mkdir -p /data && chown 10001:10001 /data
COPY --chown=10001:10001 . .
USER 10001:10001
EXPOSE 5001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5001"]
