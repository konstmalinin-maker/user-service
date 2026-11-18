"""Общие типы контракта и ошибки репозитория."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class Error(BaseModel):
    error: str


class StorageError(Exception):
    pass


class ConflictError(Exception):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
