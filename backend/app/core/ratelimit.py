from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException


_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(
    key: str,
    *,
    max_hits: int,
    window_s: float,
    detail: str,
) -> None:
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and now - bucket[0] > window_s:
        bucket.popleft()
    if len(bucket) >= max_hits:
        wait = max(1, int(window_s - (now - bucket[0])) + 1)
        raise HTTPException(
            status_code=429,
            detail=f"{detail} Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    bucket.append(now)
