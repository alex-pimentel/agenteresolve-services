"""Tool registry facade.

The canonical catalogue lives in :mod:`common.catalog`; this module exposes it to the
gateway and translates unknown slugs into HTTP 404.
"""

from common.catalog import CATALOG, SLUGS, ToolSpec, get_tool
from fastapi import HTTPException, status


def list_tools() -> list[ToolSpec]:
    return list(CATALOG.values())


def resolve(slug: str) -> ToolSpec:
    try:
        return get_tool(slug)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool '{slug}'",
        ) from exc


__all__ = ["SLUGS", "list_tools", "resolve"]
