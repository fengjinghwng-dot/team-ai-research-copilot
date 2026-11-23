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
    return OpenAI(api_key=cfg.openai_api_key, max_retries=0, timeout=120)


def structured(team_id, model: str, purpose: str, prompt: str, data: dict, schema, max_output: int = 3500):
    api = client()
    request_text = json.dumps(data, ensure_ascii=False)
    # UTF-8 byte count conservatively exceeds byte-BPE input tokens; include schema + framing headroom.
    upper = len((prompt + request_text + json.dumps(schema.model_json_schema())).encode()) + max_output + 8192
    call = reserve(team_id, model, purpose, upper)
    try:
        response = api.responses.parse(
            model=model, store=False,
            input=[{"role": "system", "content": prompt}, {"role": "user", "content": request_text}],
            text_format=schema, max_output_tokens=max_output,
        )
    except Exception:
        uncertain(call)
        raise
    if response.usage:
        settle(call, response.usage.input_tokens + response.usage.output_tokens)
    else:
        uncertain(call)
    if response.status != "completed" or response.output_parsed is None:
        raise ValueError("Model refused, returned incomplete output, or failed schema validation")
    return response.output_parsed


def embed(team_id, texts: list[str]) -> list[list[float]]:
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
