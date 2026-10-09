
import base64
import json
import logging
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class GemmaClient:
    """
    Client for local Gemma inference.

    Providers:
        - ollama
        - openai_compatible
        - mock

    Supports text generation, image input, JSON parsing,
    and model/server health checks.
    """

    def __init__(
        self,
        provider: str = "ollama",
        model_name: str = "gemma4:e2b",
        base_url: str = "http://localhost:11434",
        api_key: str = "local",
        timeout: int = 180,
    ):
        self.provider = provider.lower().strip()
        self.model_name = model_name.strip()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

        self.session = requests.Session()

    # ---------------------------------------------------------
    # HEALTH CHECK
    # ---------------------------------------------------------

    def check_health(self) -> Dict[str, Any]:
        """Check server availability and selected model."""

        if self.provider == "mock":
            return {
                "status": "ok",
                "provider": "mock",
                "model": "mock-gemma",
            }

        try:
            if self.provider == "ollama":
                response = self.session.get(
                    f"{self.base_url}/api/tags",
                    timeout=5,
                )
                response.raise_for_status()

                models = [
                    item.get("name", "")
                    for item in response.json().get("models", [])
                ]

                installed = self.model_name in models

                # Some Ollama responses may omit the default :latest tag.
                if not installed and ":" not in self.model_name:
                    installed = f"{self.model_name}:latest" in models

                return {
                    "status": "ok" if installed else "model_not_installed",
                    "provider": "ollama",
                    "selected_model": self.model_name,
                    "available_models": models,
                    "model_installed": installed,
                }

            if self.provider == "openai_compatible":
                response = self.session.get(
                    f"{self.base_url}/models",
                    headers=self._auth_headers(),
                    timeout=5,
                )
                response.raise_for_status()

                return {
                    "status": "ok",
                    "provider": "openai_compatible",
                    "selected_model": self.model_name,
                }

            return {
                "status": "unsupported_provider",
                "provider": self.provider,
            }

        except requests.RequestException as exc:
            logger.warning("Health check failed: %s", exc)

            return {
                "status": "offline",
                "provider": self.provider,
                "error": str(exc),
            }

    # ---------------------------------------------------------
    # PUBLIC GENERATION METHOD
    # ---------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        image_base64: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generate text or analyze an image with the selected model."""

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if self.provider == "mock":
            return self._mock_generate(prompt)

        if image_base64:
            image_base64 = self._normalize_base64(image_base64)

        if self.provider == "ollama":
            return self._generate_ollama(
                prompt,
                system_prompt,
                image_base64,
                temperature,
            )

        if self.provider == "openai_compatible":
            return self._generate_openai_compatible(
                prompt,
                system_prompt,
                image_base64,
                temperature,
            )

        raise ValueError(
            f"Unsupported provider: {self.provider}"
        )

    # ---------------------------------------------------------
    # JSON GENERATION
    # ---------------------------------------------------------

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        image_base64: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Generate a response and parse it as a JSON object."""

        json_instruction = """
Return only one valid JSON object.
Do not include Markdown fences or explanations.
Use double quotes for JSON keys and string values.
Represent unknown or unreadable diagram details as uncertain.
Do not invent entities, columns, or relationships.
"""

        full_prompt = f"{prompt.strip()}\n\n{json_instruction}"

        raw_output = self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            image_base64=image_base64,
            temperature=temperature,
        )

        result = self._extract_json(raw_output)

        if "error" in result:
            raise ValueError(
                "The model did not return valid JSON. "
                f"Details: {result.get('raw_text', '')[:300]}"
            )

        return result

    # ---------------------------------------------------------
    # OLLAMA API
    # ---------------------------------------------------------
    def _generate_ollama(
            self,
            prompt,
            system_prompt=None,
            image_base64=None,
            temperature=0.2
    ):
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "5m",
            "options": {
                "temperature": temperature
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        if image_base64:
            payload["images"] = [image_base64]

        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=(10, self.timeout)
            )
            response.raise_for_status()
            data = response.json()

            result = data.get("response", "").strip()
            if not result:
                raise RuntimeError("Ollama returned an empty response.")

            return result

        except requests.exceptions.Timeout as exc:
            logger.exception("Ollama request timed out.")
            raise RuntimeError(
                f"Ollama model '{self.model_name}' exceeded the "
                f"{self.timeout}-second response timeout. "
                "Try a smaller image or a faster model."
            ) from exc

        except requests.exceptions.RequestException as exc:
            logger.exception("Ollama request failed.")
            raise RuntimeError(
                f"Could not get a response from Ollama: {exc}"
            ) from exc


    # ---------------------------------------------------------
    # OPENAI-COMPATIBLE API
    # ---------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        """Build authorization headers."""

        headers = {
            "Content-Type": "application/json",
        }

        if self.api_key and self.api_key != "local":
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _generate_openai_compatible(
        self,
        prompt: str,
        system_prompt: Optional[str],
        image_base64: Optional[str],
        temperature: float,
    ) -> str:
        """Send a request to a compatible chat-completions endpoint."""

        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        user_content: Any = prompt

        if image_base64:
            user_content = [
                {
                    "type": "text",
                    "text": prompt,
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/jpeg;base64,"
                            f"{image_base64}"
                        ),
                    },
                },
            ]

        messages.append({
            "role": "user",
            "content": user_content,
        })

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        response = self.session.post(
            f"{self.base_url}/chat/completions",
            headers=self._auth_headers(),
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "Unexpected response from OpenAI-compatible API."
            ) from exc

        if isinstance(content, list):
            # Handle APIs that return content as text blocks.
            content = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                "The API returned an empty response."
            )

        return content

    # ---------------------------------------------------------
    # IMAGE BASE64 NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_base64(image_base64: str) -> str:
        """
        Accept raw Base64 or a data URL.
        Ollama expects the encoded image data without the data URL prefix.
        """

        value = image_base64.strip()

        if value.startswith("data:") and "," in value:
            value = value.split(",", 1)[1]

        try:
            decoded = base64.b64decode(
                value,
                validate=True,
            )

            if not decoded:
                raise ValueError("Image data is empty.")

        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError(
                "image_base64 must contain valid Base64-encoded image data."
            ) from exc

        return value

    # ---------------------------------------------------------
    # JSON EXTRACTION
    # ---------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Extract a JSON object from a model response."""

        if not isinstance(text, str) or not text.strip():
            return {
                "error": "Empty model response",
                "raw_text": text or "",
            }

        cleaned = text.strip()

        # Remove optional Markdown fences.
        fence_match = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```",
            cleaned,
            re.IGNORECASE,
        )

        if fence_match:
            cleaned = fence_match.group(1).strip()

        # Try parsing the complete response.
        try:
            result = json.loads(cleaned)

            if isinstance(result, dict):
                return result

            return {
                "error": "JSON response must be an object",
                "raw_text": cleaned,
            }

        except json.JSONDecodeError:
            pass

        # Find a JSON object inside surrounding text.
        decoder = json.JSONDecoder()

        for match in re.finditer(r"\{", cleaned):
            try:
                result, _ = decoder.raw_decode(cleaned[match.start():])

                if isinstance(result, dict):
                    return result

            except json.JSONDecodeError:
                continue

        # Do not silently treat malformed output as a valid schema.
        logger.error(
            "Failed to parse JSON response: %s",
            cleaned[:300],
        )

        return {
            "error": "Failed to parse JSON response from model",
            "raw_text": cleaned,
        }

    # ---------------------------------------------------------
    # OPTIONAL MOCK PROVIDER
    # ---------------------------------------------------------

    def _mock_generate(self, prompt: str) -> str:
        """
        Basic mock response for testing application wiring.
        This does not analyze images or represent actual AI inference.
        """

        return json.dumps({
            "status": "mock_response",
            "message": (
                "Mock provider is active. No real image analysis "
                "or schema extraction was performed."
            ),
            "prompt_received": prompt[:200],
        })