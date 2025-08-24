import asyncio
import functools
import logging
import time

logger = logging.getLogger(__name__)


class Profiler:
    """
    Provides a decorator to profile synchronous and asynchronous methods,
    logging their execution times.
    """

    @staticmethod
    def profile(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[Profiler] {func.__qualname__} took {elapsed:.4f}s")
                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[Profiler] {func.__qualname__} took {elapsed:.4f}s")
                return result

            return sync_wrapper
