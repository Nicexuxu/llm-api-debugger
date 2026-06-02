from copy import deepcopy

DEFAULT_PARAMS = {
    "temperature": None,
    "max_tokens": None,
    "top_p": None,
    "stop": None,
    "frequency_penalty": None,
    "presence_penalty": None,
    "seed": None,
    "thinking": None,
    "reasoning_effort": None,
    "tools": None,
}


def build_payload(model: str, messages: list[dict], params: dict, tools: list[dict] | None = None,
                  thinking: dict | None = None, reasoning_effort: str | None = None) -> dict:
    payload: dict = {
        "model": model,
        "messages": deepcopy(messages),
    }
    for key, default in DEFAULT_PARAMS.items():
        val = params.get(key, default)
        if val is not None:
            payload[key] = val
    if tools:
        payload["tools"] = deepcopy(tools)
    if thinking:
        payload["thinking"] = deepcopy(thinking)
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    return payload


def build_full_request(settings, payload: dict) -> dict:
    return {
        "method": "POST",
        "url": f"{settings.base_url}/chat/completions",
        "headers": {
            "Authorization": f"Bearer {settings.api_key[:7]}...",
            "Content-Type": "application/json",
        },
        "body": payload,
    }
