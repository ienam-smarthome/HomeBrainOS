from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import requests


@dataclass
class MakerApiConfig:
    base_url: str
    app_id: str
    token: str


class HubitatMakerApi:
    def __init__(self, config: MakerApiConfig) -> None:
        self.config = config

    def _url(self, path: str) -> str:
        base = self.config.base_url.rstrip('/')
        sep = '&' if '?' in path else '?'
        return f'{base}/apps/api/{self.config.app_id}/{path}{sep}access_token={self.config.token}'

    def devices(self) -> list[dict[str, Any]]:
        response = requests.get(self._url('devices'), timeout=15)
        response.raise_for_status()
        return response.json()

    def command(self, device_id: str, command: str) -> Any:
        response = requests.get(self._url(f'devices/{device_id}/{command}'), timeout=10)
        response.raise_for_status()
        try:
            return response.json()
        except Exception:
            return {'success': True}
