"""LangFuse tracing helpers.

`@trace_node(name)` wraps a LangGraph node coroutine and emits a span with the
node's input / output / model / token usage. When `LANGFUSE_ENABLED=false` (the
default), the wrapper is a no-op so unit tests don't need a running LangFuse.

Usage:

    @trace_node("nigel.write")
    async def nigel_write(state): ...

The decorator inspects the state's `run_id` to attach the span to the day's trace.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from app.config import get_settings

log = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])

_client_singleton: Any | None = None


def _client() -> Any | None:
    """Return a cached `langfuse.Langfuse` client, or None when disabled."""
    global _client_singleton
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    if _client_singleton is not None:
        return _client_singleton
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        log.warning("LANGFUSE_ENABLED=true but keys are blank; tracing disabled")
        return None
    try:
        from langfuse import Langfuse

        _client_singleton = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return _client_singleton
    except Exception as exc:  # pragma: no cover — depends on prod env
        log.warning("failed to init Langfuse client: %s", exc)
        return None


@contextmanager
def _span(
    name: str, run_id: str, input_payload: dict[str, Any]
) -> Iterator[Any]:
    """Yield a span object that has `.end(output=...)`. Best-effort — never raises."""
    client = _client()
    if client is None:
        yield _NoopSpan()
        return
    try:
        trace = client.trace(id=run_id, name="daily-slop-run")
        observation = trace.span(name=name, input=input_payload)
        try:
            yield observation
        finally:
            try:
                observation.end()
            except Exception:  # pragma: no cover
                log.debug("langfuse end() failed", exc_info=True)
    except Exception:
        # Tracing must never break the pipeline.
        log.debug("langfuse span failed for %s", name, exc_info=True)
        yield _NoopSpan()


class _NoopSpan:
    def update(self, **_: Any) -> None: ...

    def end(self, **_: Any) -> None: ...


def trace_node(name: str) -> Callable[[_F], _F]:
    """Decorator to wrap a LangGraph node coroutine with a LangFuse span.

    The wrapped function must be `async def fn(state) -> state`. We extract `run_id`
    from the state if present so the span attaches to the right trace.
    """

    def decorator(fn: _F) -> _F:
        @functools.wraps(fn)
        async def wrapper(state: dict[str, Any], *a: Any, **kw: Any) -> Any:
            run_id = str(state.get("run_id") or "unknown-run")
            with _span(name, run_id, {"section": state.get("section"), "writer": state.get("writer")}) as obs:
                result = await fn(state, *a, **kw)
                try:
                    output = {
                        "status": result.get("status"),
                        "verdict": result.get("editor_verdict"),
                        "writer": result.get("writer"),
                        "pushback_used": result.get("pushback_used"),
                        "revision_count": result.get("revision_count"),
                    }
                    obs.update(output=output)
                except Exception:
                    log.debug("trace output update failed for %s", name, exc_info=True)
                return result

        return wrapper  # type: ignore[return-value]

    return decorator


def flush() -> None:
    """Force-flush pending spans. Call at the end of `run_daily`."""
    client = _client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:  # pragma: no cover
        log.debug("langfuse flush failed", exc_info=True)
