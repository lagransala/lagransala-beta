import os

import instructor
from anthropic import AsyncAnthropic
from groq import AsyncGroq
from redis import StrictRedis
from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine

_SQLMODEL: Engine | None = None


def initialize_sqlmodel() -> Engine:
    global _SQLMODEL
    if not _SQLMODEL:
        _SQLMODEL = create_engine(
            "sqlite:///lagransala.db",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(_SQLMODEL)
    return _SQLMODEL


_INSTRUCTOR: instructor.AsyncInstructor | None = None

INSTRUCTOR_MODEL = "deepseek-r1-distill-llama-70b"


def initialize_instructor_anthropic() -> instructor.AsyncInstructor:
    global _INSTRUCTOR
    if not _INSTRUCTOR:
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        assert (
            anthropic_api_key
        ), "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY"

        _INSTRUCTOR = instructor.from_anthropic(
            AsyncAnthropic(api_key=anthropic_api_key)
        )
    return _INSTRUCTOR


def initialize_instructor_groq() -> instructor.AsyncInstructor:
    global _INSTRUCTOR
    if not _INSTRUCTOR:
        groq_api_key = os.getenv("GROQ_API_KEY")
        assert (
            groq_api_key
        ), "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY"
        _INSTRUCTOR = instructor.from_groq(
            AsyncGroq(api_key=groq_api_key), mode=instructor.Mode.TOOLS
        )
    return _INSTRUCTOR


_REDIS: StrictRedis | None = None


def initialize_redis() -> StrictRedis:
    global _REDIS
    if not _REDIS:
        _REDIS = StrictRedis(host="localhost", decode_responses=True)
    return _REDIS
