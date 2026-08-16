from typing import Tuple

MODEL_PRICING = {
    "anthropic": {
        "claude-3-5-sonnet": (0.003, 0.015),
        "claude-3-haiku": (0.00025, 0.00125),
        "claude-3-opus": (0.015, 0.075),
    },
    "openai": {
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4o": (0.0025, 0.01),
        "gpt-4-turbo": (0.01, 0.03),
    },
    "google": {
        "gemini-1.5-flash": (0.000075, 0.0003),
        "gemini-1.5-pro": (0.00125, 0.005),
        "gemini-2.0-flash": (0.0001, 0.0004),
    }
}

DEFAULT_PRICING = (0.001, 0.003)

def calculate_ai_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    prov_key = (provider or "").lower()
    mod_key = (model or "").lower()

    pricing = DEFAULT_PRICING
    if prov_key in MODEL_PRICING:
        # Sort model keys by length descending to match specific models first (e.g. gpt-4o-mini before gpt-4o)
        sorted_models = sorted(MODEL_PRICING[prov_key].items(), key=lambda x: len(x[0]), reverse=True)
        for m_name, p_rate in sorted_models:
            if m_name in mod_key:
                pricing = p_rate
                break

    in_cost = (input_tokens / 1000.0) * pricing[0]
    out_cost = (output_tokens / 1000.0) * pricing[1]
    return round(in_cost + out_cost, 6)
