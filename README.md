# User Service — практическая работа №8

![CI](https://github.com/konstmalinin-maker/user-service/actions/workflows/ci.yml/badge.svg?branch=main)

Самостоятельный REST-сервис пользователей на FastAPI и SQLite.
Контракт: [docs/api-contract.md](docs/api-contract.md), [OpenAPI](docs/openapi.json).
Docker: `ghcr.io/konstmalinin-maker/user-service:latest`.

| Метод | Путь | Результат |
|---|---|---|
| POST | /users | 201: создание пользователя |
| GET | /users | 200: список |
| GET | /users/{user_id} | 200 / 404 |
| PUT | /users/{user_id} | 200 / 400 / 404 |
| DELETE | /users/{user_id} | 204 / 404 |
| GET | /health | 200, локальное состояние SQLite |

Некорректные данные и повторный email — 400; сбой SQLite — 503.
DATA_PATH задаёт файл БД. Для запуска без Docker: `uvicorn app.main:app --port 5001`.

## Быстрый запуск полного стенда

Нужны Git, Docker Engine с Compose v2 и свободные порты 80, 3000, 9090, 15672, 16686.
Репозитории должны лежать рядом:

```bash
git clone https://github.com/konstmalinin-maker/user-service.git
git clone https://github.com/konstmalinin-maker/order-service.git
cd order-service
docker compose build
docker compose up -d --no-build --wait
docker compose ps
```

Клиентские запросы идут через Nginx: `http://localhost/api/users`,
`http://localhost/api/orders`. Межсервисный адрес — `http://user-service:5001`.
В обычном Docker порты API наружу не публикуются.

```bash
curl -i -X POST http://localhost/api/users -H 'Content-Type: application/json' -d '{"email":"student@example.com","name":"Student"}'
curl -i -X POST http://localhost/api/orders -H 'Content-Type: application/json' -d '{"user_id":1,"total":1250.50}'
curl http://localhost/api/orders
```

Лимит Nginx — 10 запросов/с с одного IP, превышение даёт 429.
Учебные RabbitMQ: `lab` / `lab-demo`. Доступ к интерфейсам ограничен loopback.
Grafana использует анонимную роль Viewer. Такие настройки предназначены для локальной лаборатории.

| Интерфейс | Адрес |
|---|---|
| Swagger User | http://localhost/docs/users/docs |
| Swagger Order | http://localhost/docs/orders/docs |
| RabbitMQ | http://localhost:15672 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000/d/pr8/ |
| Jaeger | http://localhost:16686 |

SQLite-файлы раздельные: users-data, orders-data, notifications-data.
`docker compose restart` и `docker compose down` сохраняют данные.
`docker compose down -v` удаляет учебные данные.
Общий том SQLite нескольких реплик используется только на одном узле kind;
для промышленного кластера нужен серверный SQL и миграции.

## Проверки

Python 3.12:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
ruff check .
python -m pytest -q --cov --cov-fail-under=80
```

CI выполняет Ruff, pytest и контроль покрытия не ниже 80%, собирает Docker.
При push в main образ публикуется в GHCR с тегами latest и SHA коммита.
Точный digest сохраняется в артефакте image-digest.
Контракты в docs зафиксированы отдельным коммитом до реализации.

## Дополнительные задания

A — SQLite, слой репозиториев, WAL, постоянные тома, изолированные БД тестов.
B — FastAPI/Pydantic, локальные Swagger assets, generated SDK openapi-python-client.
C — Nginx, порт 80, маршрутизация и ограничение 10 запросов/с.
D — RabbitMQ, transactional outbox, отдельный notification-service, manual ACK,
идемпотентная запись уведомлений и интеграционный тест.
E — prometheus-flask-exporter через WSGI-монтирование Flask в FastAPI,
метрики запросов/latency/ошибок/breaker, Prometheus и готовый дашборд Grafana.
F — OpenTelemetry SDK, HTTPX-инструментация, общий контекст traceparent, Jaeger.
G — CI/CD обоих репозиториев, покрытие и GHCR.
H — Deployment/Service/ConfigMap/PVC, probes и проверенное масштабирование kind до 3 реплик.
