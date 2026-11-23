import json

from openai import OpenAI

from .budget import reserve, settle, uncertain
from .config import settings


class LLMDisabled(RuntimeError):
    pass


def client():
    cfg = settings()
    if not cfg.llm_enabled:
        raise LLMDisabled("LLM disabled: metadata-only mode")
    # No implicit retries: an ambiguous timeout must not create unaccounted repeat charges.
    if cfg.llm_provider == "deepseek":
        return OpenAI(api_key=cfg.deepseek_api_key, base_url="https://api.deepseek.com",
                      max_retries=0, timeout=120)
    return OpenAI(api_key=cfg.openai_api_key, max_retries=0, timeout=120)


def structured(team_id, model: str, purpose: str, prompt: str, data: dict, schema, max_output: int = 3500):
    cfg = settings()
    if cfg.llm_provider == "deepseek" and model != "deepseek-flash":
        raise ValueError("Unpriced DeepSeek model; refusing a call outside the budget guard")
    api = client()
    request_text = json.dumps(data, ensure_ascii=False)
    # UTF-8 byte count conservatively exceeds byte-BPE input tokens; include schema + framing headroom.
    upper = len((prompt + request_text + json.dumps(schema.model_json_schema())).encode()) + max_output + 8192
    call = reserve(team_id, model, purpose, upper)
    try:
        provider_options = {"reasoning": {"effort": "none"}} if cfg.llm_provider == "deepseek" else {}
        response = api.responses.parse(
            model=model, store=False,
            input=[{"role": "system", "content": prompt}, {"role": "user", "content": request_text}],
            text_format=schema, max_output_tokens=max_output, **provider_options,
        )
    except Exception:
        uncertain(call)
        raise
    if response.usage:
        usage = response.usage
        settle(call, usage.input_tokens + usage.output_tokens, input_tokens=usage.input_tokens,
               output_tokens=usage.output_tokens,
               cached_input_tokens=getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0)
    else:
        uncertain(call)
    if response.status != "completed" or response.output_parsed is None:
        raise ValueError("Model refused, returned incomplete output, or failed schema validation")
    return response.output_parsed


def embed(team_id, texts: list[str]) -> list[list[float]]:
    if settings().llm_provider == "deepseek":
        raise LLMDisabled("DeepSeek has no configured embedding provider; use keyword search")
    api = client()
    # Keep embedding requests within the embedding context, independent of report size.
    texts = [text.encode("utf-8")[:6000].decode("utf-8", errors="ignore") for text in texts]
    upper = sum(len(text.encode()) for text in texts) + 1024
    call = reserve(team_id, settings().embedding_model, "embedding", upper)
    try:
        response = api.embeddings.create(model=settings().embedding_model, input=texts, dimensions=1536)
    except Exception:
        uncertain(call)
        raise
    settle(call, response.usage.total_tokens)
    return [row.embedding for row in response.data]
