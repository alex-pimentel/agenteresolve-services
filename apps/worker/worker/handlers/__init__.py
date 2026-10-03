"""Tool handler registry.

Only ``translate`` is implemented end-to-end. The remaining 15 slugs are registered in
the catalogue as stubs and rejected by the gateway with HTTP 501 before a job is created.
"""

from collections.abc import Callable

from worker.handlers.base import HandlerContext, HandlerResult
from worker.handlers.translate import handle_translate

Handler = Callable[[HandlerContext], HandlerResult]

HANDLERS: dict[str, Handler] = {
    "translate": handle_translate,
}


def get_handler(slug: str) -> Handler:
    handler = HANDLERS.get(slug)
    if handler is None:
        raise KeyError(f"No handler registered for tool '{slug}'")
    return handler


__all__ = ["HANDLERS", "Handler", "get_handler", "handle_translate"]
