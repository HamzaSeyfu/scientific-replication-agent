from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass
class NemotronClient:
    api_key: str
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    base_url: str = "https://api.tokenfactory.nebius.com/v1/"

    @classmethod
    def from_env(cls) -> "NemotronClient":
        key = os.environ.get("NEBIUS_API_KEY")
        if not key:
            raise RuntimeError("NEBIUS_API_KEY is not set")
        return cls(
            api_key=key,
            model=os.environ.get("NEBIUS_MODEL", cls.model),
            base_url=os.environ.get("NEBIUS_BASE_URL", cls.base_url),
        )

    def _client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def json_response(self, *, system: str, user: str) -> dict[str, Any]:
        response = self._client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
