from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import requests


DEFAULT_API_BASE = "https://api.openai.com/v1"


class OpenAIAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class StructuredResult:
    value: dict[str, Any]
    response_id: str
    model: str
    usage: dict[str, Any]


class OpenAIAPIClient:
    """Minimal API client that keeps this audit's dependency surface small."""

    def __init__(
        self,
        api_key: str,
        *,
        api_base: str = DEFAULT_API_BASE,
        timeout_seconds: int = 180,
        max_retries: int = 5,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("An OpenAI API key is required")
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def _post(self, endpoint: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    json=dict(payload),
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise OpenAIAPIError(
                        f"OpenAI request failed after {attempt + 1} attempts: {exc}"
                    ) from exc
                time.sleep(min(2**attempt, 20))
                continue

            if response.status_code < 400:
                try:
                    value = response.json()
                except ValueError as exc:
                    raise OpenAIAPIError(
                        "OpenAI returned a non-JSON success response"
                    ) from exc
                if not isinstance(value, dict):
                    raise OpenAIAPIError("OpenAI returned an unexpected response type")
                return value

            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = float(min(2**attempt, 20))
                time.sleep(min(max(delay, 0.25), 30.0))
                continue

            message = f"HTTP {response.status_code}"
            try:
                error_body = response.json()
                if isinstance(error_body, Mapping):
                    error = error_body.get("error")
                    if isinstance(error, Mapping) and error.get("message"):
                        message = str(error["message"])[:1000]
            except ValueError:
                pass
            raise OpenAIAPIError(f"OpenAI request failed: {message}")

        raise AssertionError("Retry loop exited unexpectedly")

    def create_embeddings(
        self,
        inputs: Sequence[str],
        *,
        model: str,
        dimensions: int | None = None,
        batch_size: int = 128,
    ) -> list[list[float]]:
        if not inputs:
            return []
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        embeddings: list[list[float]] = []
        for start in range(0, len(inputs), batch_size):
            batch = list(inputs[start : start + batch_size])
            if any(not isinstance(item, str) or not item.strip() for item in batch):
                raise ValueError("Embedding inputs must be non-empty strings")
            payload: dict[str, Any] = {
                "model": model,
                "input": batch,
                "encoding_format": "float",
            }
            if dimensions is not None:
                payload["dimensions"] = dimensions
            response = self._post("embeddings", payload)
            data = response.get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise OpenAIAPIError(
                    "Embedding response count did not match the request count"
                )
            ordered = sorted(data, key=lambda item: int(item.get("index", -1)))
            for expected_index, item in enumerate(ordered):
                if not isinstance(item, Mapping) or item.get("index") != expected_index:
                    raise OpenAIAPIError("Embedding response indexes were invalid")
                vector = item.get("embedding")
                if not isinstance(vector, list) or not vector:
                    raise OpenAIAPIError("Embedding response contained no vector")
                embeddings.append([float(value) for value in vector])
        return embeddings

    def create_structured_response(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: Mapping[str, Any],
        reasoning_effort: str = "medium",
        max_output_tokens: int = 4000,
    ) -> StructuredResult:
        payload: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": [{"role": "user", "content": input_text}],
            "max_output_tokens": max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": dict(schema),
                }
            },
        }
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}

        response = self._post("responses", payload)
        if response.get("status") != "completed":
            error = response.get("error") or response.get("incomplete_details")
            raise OpenAIAPIError(
                f"OpenAI response did not complete successfully: {error!r}"
            )

        output_texts: list[str] = []
        refusals: list[str] = []
        output = response.get("output")
        if not isinstance(output, list):
            raise OpenAIAPIError("OpenAI response contained no output array")
        for item in output:
            if not isinstance(item, Mapping) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, Mapping):
                    continue
                if block.get("type") == "output_text" and isinstance(
                    block.get("text"), str
                ):
                    output_texts.append(block["text"])
                elif block.get("type") == "refusal":
                    refusals.append(str(block.get("refusal", "Model refusal")))

        if refusals:
            raise OpenAIAPIError("OpenAI refused the duplicate judgment request")
        if not output_texts:
            raise OpenAIAPIError("OpenAI response contained no output text")
        try:
            parsed = json.loads("".join(output_texts))
        except json.JSONDecodeError as exc:
            raise OpenAIAPIError(
                "OpenAI structured response could not be decoded as JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise OpenAIAPIError("OpenAI structured response was not an object")

        usage = response.get("usage")
        return StructuredResult(
            value=parsed,
            response_id=str(response.get("id", "")),
            model=str(response.get("model", model)),
            usage=dict(usage) if isinstance(usage, Mapping) else {},
        )
