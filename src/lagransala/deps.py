import os

import instructor
from anthropic import AsyncAnthropic

# import google.generativeai as genai
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


# def initialize_instructor_gemini() -> instructor.AsyncInstructor:
#     gemini_api_key= os.getenv("GEMINI_API_KEY")
#     assert (
#         gemini_api_key
#     ), "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY"
#     genai.client.configure(api_key=gemini_api_key)

#     model = genai.generative_models.GenerativeModel(
#       model_name="gemini-2.0-flash",
#     )
#     return instructor.from_gemini(model, use_async=True)
