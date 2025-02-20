import json
from typing import Type, TypeVar

from sqlmodel import AutoString

T = TypeVar("T")


def build_sqlmodel_type(internal_type: Type[T]) -> Type[AutoString]:
    class CustomType(AutoString):
        def process_bind_param(self, value, dialect) -> str | None:
            if value is None:
                return None

            if isinstance(value, str):
                # Test if value is valid to avoid `process_result_value` failling
                try:
                    internal_type(value)  # type: ignore[call-arg]
                except ValueError as e:
                    raise ValueError(
                        f"Invalid value for {internal_type.__name__}: {e}"
                    ) from e

            return str(value)

        def process_result_value(self, value, dialect) -> T | None:
            if value is None:
                return None

            return internal_type(value)  # type: ignore[call-arg]

    return CustomType


def build_sqlmodel_list_type(internal_type: Type[T]) -> Type[AutoString]:
    class CustomType(AutoString):
        def process_bind_param(self, value, dialect) -> str | None:
            if value is None:
                return None

            if isinstance(value, str):
                # Test if value is valid to avoid `process_result_value` failling
                try:
                    values = json.loads(value)
                    assert isinstance(values, list)
                    for v in values:
                        internal_type(v)  # type: ignore[call-arg]
                except ValueError as e:
                    raise ValueError(
                        f"Invalid value for {internal_type.__name__}: {e}"
                    ) from e

            return json.dumps(value)

        def process_result_value(self, value, dialect) -> list[T] | None:
            if value is None:
                return None
            return [internal_type(v) for v in json.loads(value)]  # type: ignore[call-arg]

    return CustomType
