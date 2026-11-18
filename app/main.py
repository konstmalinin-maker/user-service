"""FastAPI user-service: CRUD, OpenAPI, метрики и трассировка."""

import os
import sqlite3
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common_models import ConflictError, Error, StorageError
from app.models import User, UserInput
from app.observability import configure_observability, local_swagger
from app.repositories import UserRepository


def create_app(db_path=None):
    app = FastAPI(title="User Service", version="1.0.0", docs_url=None, redoc_url=None)
    repo = UserRepository(db_path or os.getenv("DATA_PATH", "users.sqlite3"))
    app.state.repo = repo
    configure_observability(app, "user-service")
    local_swagger(app)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Некорректные данные запроса",
                "details": [{"field": ".".join(str(v) for v in x["loc"]), "message": x["msg"]} for x in exc.errors()],
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

    @app.exception_handler(ConflictError)
    async def conflict(request, exc):
        return JSONResponse(status_code=400, content={"error": str(exc)})

    @app.exception_handler(StorageError)
    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        return JSONResponse(status_code=503, content={"error": "Хранилище пользователей недоступно"})

    @app.get("/health", operation_id="health")
    def health():
        repo.ready()
        return {"status": "ok", "service": "user-service", "storage": "sqlite"}

    @app.post(
        "/users",
        response_model=User,
        status_code=201,
        tags=["users"],
        operation_id="create_user",
        responses={400: {"model": Error}},
    )
    def create_user(data: UserInput):
        return repo.create(str(data.email), data.name)

    @app.get("/users", response_model=list[User], tags=["users"], operation_id="list_users")
    def list_users():
        return repo.list_all()

    @app.get(
        "/users/{user_id}",
        response_model=User,
        tags=["users"],
        operation_id="get_user",
        responses={404: {"model": Error}, 400: {"model": Error}},
    )
    def get_user(user_id: Annotated[int, Path(gt=0)]):
        user = repo.get(user_id)
        if user is None:
            raise HTTPException(404, "Пользователь не найден")
        return user

    @app.put(
        "/users/{user_id}",
        response_model=User,
        tags=["users"],
        operation_id="update_user",
        responses={404: {"model": Error}, 400: {"model": Error}},
    )
    def update_user(user_id: Annotated[int, Path(gt=0)], data: UserInput):
        user = repo.update(user_id, str(data.email), data.name)
        if user is None:
            raise HTTPException(404, "Пользователь не найден")
        return user

    @app.delete(
        "/users/{user_id}",
        status_code=204,
        tags=["users"],
        operation_id="delete_user",
        responses={404: {"model": Error}},
    )
    def delete_user(user_id: Annotated[int, Path(gt=0)]):
        if not repo.delete(user_id):
            raise HTTPException(404, "Пользователь не найден")
        return Response(status_code=204)

    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        for operations in schema["paths"].values():
            for operation in operations.values():
                if isinstance(operation, dict):
                    operation.get("responses", {}).pop("422", None)
        return schema

    app.openapi = openapi
    return app


app = create_app()
