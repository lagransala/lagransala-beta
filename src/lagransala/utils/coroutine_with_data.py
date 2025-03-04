from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")
D = TypeVar("D")
R = TypeVar("R")


async def coroutine_with_data(
    coroutine: Coroutine[Any, Any, T],
    data: D,
    combiner: Callable[[T, D], R],
) -> R:
    result = await coroutine
    return combiner(result, data)
