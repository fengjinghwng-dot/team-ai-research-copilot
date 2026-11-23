"""Persistent cache for public research sources. No credentials in keys or cache bodies."""
import hashlib
import json
import time
from datetime import timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .db import session
from .models import FetchCache, utcnow


class FetchError(RuntimeError):
    pass


class Fetcher:
    hosts = {"export.arxiv.org", "arxiv.org", "api.semanticscholar.org", "huggingface.co"}

    def __init__(self, cache_only: bool | None = None):
        self.cache_only = settings().use_cache_only if cache_only is None else cache_only
        self.last_arxiv = 0.0

    def get(self, url: str, params: dict | None = None, max_bytes: int = 12_000_000,
            permanent: bool = False) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.hosts:
            raise FetchError("Source URL is outside the approved research hosts")
        key = hashlib.sha256((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        with session() as db:
            cached = db.get(FetchCache, key)
            if cached and (self.cache_only or permanent or
                           cached.created_at > utcnow() - timedelta(hours=settings().http_cache_hours)):
                return cached.body
        if self.cache_only:
            raise FetchError("Public source cache miss in --use-cache mode")
        headers = {"User-Agent": settings().source_user_agent}
        if parsed.hostname == "api.semanticscholar.org" and settings().semantic_scholar_api_key:
            headers["x-api-key"] = settings().semantic_scholar_api_key
        # Single pipeline lock ensures this process is the only ingestion worker.
        for attempt in range(3):
            if "arxiv.org" in parsed.hostname:
                time.sleep(max(0, 3.1 - (time.monotonic() - self.last_arxiv)))
                self.last_arxiv = time.monotonic()
            try:
                with httpx.Client(timeout=45, follow_redirects=False) as client:
                    with client.stream("GET", url, params=params, headers=headers) as response:
                        if response.status_code in {429, 502, 503, 504} and attempt < 2:
                            retry = response.headers.get("retry-after", "")
                            time.sleep(min(45, max(3, int(retry) if retry.isdigit() else 3 ** (attempt + 1))))
                            continue
                        response.raise_for_status()
                        data = bytearray()
                        for chunk in response.iter_bytes():
                            data.extend(chunk)
                            if len(data) > max_bytes:
                                raise FetchError("Source exceeds download size limit")
                        content_type = response.headers.get("content-type", "")[:200]
                body = bytes(data)
                with session() as db:
                    db.execute(insert(FetchCache).values(key=key, body=body, content_type=content_type)
                               .on_conflict_do_update(index_elements=["key"], set_={
                                   "body": body, "content_type": content_type, "created_at": utcnow()}))
                return body
            except httpx.HTTPError as exc:
                if attempt == 2 or (isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500):
                    # Avoid logging request URLs that could someday contain sensitive query data.
                    raise FetchError(f"Source request failed: {type(exc).__name__}") from None
                time.sleep(3 ** (attempt + 1))
        raise FetchError("Source retries exhausted")

    def json(self, url: str, params: dict | None = None):
        return json.loads(self.get(url, params=params))
