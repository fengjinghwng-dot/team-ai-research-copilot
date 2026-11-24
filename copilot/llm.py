import json

from openai import LengthFinishReasonError, OpenAI

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
    if cfg.llm_provider == "openai_compatible":
        return OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url, max_retries=0, timeout=120)
    return OpenAI(api_key=cfg.openai_api_key, max_retries=0, timeout=120)


def settle_chat(call, response):
    if response.usage:
        usage = response.usage
        settle(call, usage.prompt_tokens + usage.completion_tokens, input_tokens=usage.prompt_tokens,
               output_tokens=usage.completion_tokens,
               cached_input_tokens=getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0)
    else:
        uncertain(call)


def structured(team_id, model: str, purpose: str, prompt: str, data: dict, schema, max_output: int = 6000):
    cfg = settings()
    if cfg.llm_provider == "deepseek" and model != "deepseek-flash":
        raise ValueError("Unpriced DeepSeek model; refusing a call outside the budget guard")
    if cfg.llm_provider == "openai_compatible" and model not in {cfg.cheap_model, cfg.deep_model}:
        raise ValueError("Unpriced custom model")
    api = client()
    request_text = json.dumps(data, ensure_ascii=False)
    # UTF-8 byte count conservatively exceeds byte-BPE input tokens; include schema + framing headroom.
    upper = len((prompt + request_text + json.dumps(schema.model_json_schema())).encode()) + max_output + 8192
    call = reserve(team_id, model, purpose, upper)
    is_chat = cfg.llm_provider == "openai_compatible" and cfg.llm_api_format == "chat_completions"
    try:
        if is_chat:
            options = {"extra_body": {"thinking": {"type": "disabled"}}} if cfg.llm_thinking_mode == "disabled" else {}
            response = api.chat.completions.parse(model=model, store=False,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": request_text}],
                response_format=schema, max_tokens=max_output, **options)
        else:
            provider_options = {"reasoning": {"effort": "none"}} if cfg.llm_provider == "deepseek" else {}
            response = api.responses.parse(
                model=model, store=False,
                input=[{"role": "system", "content": prompt}, {"role": "user", "content": request_text}],
                text_format=schema, max_output_tokens=max_output, **provider_options,
            )
    except LengthFinishReasonError as error:
        if is_chat:
            settle_chat(call, error.completion)
        else:
            uncertain(call)
        raise
    except Exception:
        uncertain(call)
        raise
    if is_chat:
        settle_chat(call, response)
        choice = response.choices[0] if response.choices else None
        if not choice or choice.finish_reason != "stop" or choice.message.parsed is None or choice.message.refusal:
            raise ValueError("Model refused or failed the structured output contract")
        return choice.message.parsed
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
    if settings().llm_provider != "openai":
        raise LLMDisabled("No configured embedding provider for this endpoint; use keyword search")
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
