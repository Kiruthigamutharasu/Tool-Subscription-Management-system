import re
import time
from typing import Any
from ddgs import DDGS  # type: ignore


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        q = q.strip()
        if len(q) < 2:
            continue
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _query_variants(query: str) -> list[str]:
    base = query.strip()
    core = re.sub(r"\s+alternatives?\s*$", "", base, flags=re.I).strip()
    return _dedupe_queries(
        [
            base,
            base.replace(" pricing", "").strip(),
            f"alternatives to {core}" if core else base,
            f"{core} alternatives best" if core else base,
        ]
    )


def search_internet(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Web search via DDGS. Uses a fresh DDGS client per attempt — reusing one session
    for many text() calls often returns empty results with this library.
    """
    variants = _query_variants(query)
    backends = ["duckduckgo", "brave", "yahoo", "auto"]

    last_error: str | None = None

    for attempt in range(2):
        for q in variants:
            for backend in backends:
                try:
                    with DDGS() as ddgs:
                        raw = ddgs.text(q, max_results=max_results, backend=backend)
                    items = list(raw) if raw is not None else []
                    results: list[dict[str, Any]] = []
                    for r in items:
                        if not isinstance(r, dict):
                            continue
                        if r.get("error"):
                            last_error = str(r.get("error"))
                            continue
                        if r.get("title") or r.get("href") or r.get("body"):
                            results.append(r)
                    if results:
                        return results[:max_results]
                except Exception as e:
                    last_error = str(e)
                    continue
        if attempt == 0:
            time.sleep(0.4)

    if last_error:
        return [{"error": last_error}]
    return []
