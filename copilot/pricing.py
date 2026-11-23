"""Conservative estimates, not provider invoices. Rates last checked 2026-11-24."""
from decimal import Decimal


def deepseek_flash_upper(input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> Decimal:
    if min(input_tokens, output_tokens, cached_tokens) < 0 or cached_tokens > input_tokens:
        raise ValueError("Invalid usage counters")
    return ((Decimal(input_tokens - cached_tokens) * 2 + Decimal(cached_tokens) * Decimal("0.04") +
             Decimal(output_tokens) * 8) / 1_000_000).quantize(Decimal("0.00000001"))
