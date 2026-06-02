import json
from typing import Iterator

import httpx


class APIError(Exception):
    def __init__(self, status_code: int, message: str, body: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.body = body


class OpenAIClient:
    def __init__(self, api_key: str, base_url: str, timeout: int = 120):
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )
        self.base_url = base_url
        self.api_key = api_key

    def chat_completion(self, payload: dict) -> dict:
        return self._request("POST", "/chat/completions", payload)

    def stream_chat(self, payload: dict) -> Iterator[dict]:
        payload = {**payload, "stream": True}
        try:
            with self._client.stream("POST", "/chat/completions", json=payload) as r:
                if r.is_error:
                    body = None
                    try:
                        raw = r.read()
                        body = json.loads(raw) if raw else None
                    except Exception:
                        pass
                    msg = self._extract_error(r.status_code, body)
                    raise APIError(r.status_code, msg, body)
                for line in r.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        yield json.loads(data)
        except httpx.HTTPStatusError as e:
            raise APIError(e.response.status_code, str(e), None)

    def _request(self, method: str, endpoint: str, payload: dict) -> dict:
        try:
            r = self._client.request(method, endpoint, json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            body = None
            try:
                body = e.response.json()
            except Exception:
                pass
            msg = self._extract_error(e.response.status_code, body)
            raise APIError(e.response.status_code, msg, body)

    @staticmethod
    def _extract_error(status: int, body: dict | None) -> str:
        if body and "error" in body:
            err = body["error"]
            if isinstance(err, dict):
                return err.get("message", json.dumps(err, ensure_ascii=False))
            return str(err)
        if body and "message" in body:
            return body["message"]
        return f"HTTP {status}"

    def close(self) -> None:
        self._client.close()
