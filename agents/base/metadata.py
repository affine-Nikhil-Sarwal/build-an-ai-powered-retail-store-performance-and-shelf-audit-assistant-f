"""IO field metadata types used by agent schemas and contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class IOFieldType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    BINARY = "binary"
    ANY = "any"


class IOField(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    type: IOFieldType = IOFieldType.ANY
    description: str = ""
    required: bool = True
    example: Any = None
    semantic_type: str | None = None


__all__ = ["IOField", "IOFieldType"]
