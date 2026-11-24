"""Check a configured key using GET /models only; never submit a generation request."""
import httpx

from .config import settings


def check_provider():
    cfg = settings()
    result = {"provider": cfg.llm_provider, "llm_enabled": cfg.llm_enabled,
              "pricing_confirmed": cfg.monetary_guard_rate is not None,
              "generation_requests": 0}
    if cfg.llm_provider != "openai_compatible":
        return {**result, "ok": False, "state": "custom_provider_required"}
    result["key_configured"] = bool(cfg.llm_api_key.strip())
    if not result["key_configured"]:
        return {**result, "ok": False, "state": "key_missing"}
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get(cfg.llm_base_url.rstrip('/') + '/models',
                                  headers={"Authorization": "Bearer " + cfg.llm_api_key})
        if response.status_code != 200:
            # Provider error bodies can echo credentials; publish only the status code.
            return {**result, "ok": False, "state": "catalog_request_failed", "http_status": response.status_code}
        body = response.json()
        rows = body.get("data") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            return {**result, "ok": False, "state": "unexpected_catalog"}
        ids = {row.get("id") for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
        models = {model: model in ids for model in sorted({cfg.cheap_model, cfg.deep_model})}
        ok = all(models.values())
        return {**result, "ok": ok, "state": "ready" if ok else "model_not_listed",
                "http_status": 200, "models": models,
                "embedding_candidates": {name: name in ids for name in [
                    "text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]}}
    except (httpx.HTTPError, ValueError) as error:
        return {**result, "ok": False, "state": "catalog_request_failed", "error_type": type(error).__name__}
