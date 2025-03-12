import os

import instructor
from anthropic import AsyncAnthropic
from groq import AsyncGroq
from redis import StrictRedis
from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine


def initialize_sqlmodel() -> Engine:
    engine = create_engine(
        "sqlite:///lagransala.db", echo=False, connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


def initialize_instructor_anthropic() -> instructor.AsyncInstructor:
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    assert (
        anthropic_api_key
    ), "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY"
    return instructor.from_anthropic(AsyncAnthropic(api_key=anthropic_api_key))


def initialize_instructor_groq() -> instructor.AsyncInstructor:
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    return instructor.from_groq(client, mode=instructor.Mode.TOOLS)


_REDIS: StrictRedis | None = None


def get_redis() -> StrictRedis:
    global _REDIS
    if not _REDIS:
        _REDIS = StrictRedis(host="localhost", decode_responses=True)
    return _REDIS
