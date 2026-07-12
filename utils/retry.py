import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    exceptions: tuple[type[Exception], ...],
    max_attempts: int = 5,
    backoff_seconds: float = 0.5,
) -> T:
    """Retry an async callable on the given exceptions with linear backoff.

    Args:
        func: Zero-arg async callable to invoke.
        exceptions: Exception types that should trigger a retry.
        max_attempts: Total number of attempts before giving up.
        backoff_seconds: Base delay, multiplied by the attempt number between retries.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except exceptions as e:
            if attempt == max_attempts:
                raise
            logger.warning(
                "Attempt %d/%d failed: %s, retrying in %.1fs",
                attempt, max_attempts, e, backoff_seconds * attempt,
            )
            await asyncio.sleep(backoff_seconds * attempt)

    raise AssertionError("unreachable")
