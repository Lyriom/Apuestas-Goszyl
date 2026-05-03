import base64
import json
from typing import Any

import hvac
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings


class VaultDecryptError(RuntimeError):
    pass


class VaultService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = hvac.Client(url=str(self.settings.vault_url), token=self.settings.vault_token)

    @retry(wait=wait_exponential(multiplier=0.4, min=0.4, max=4), stop=stop_after_attempt(3), reraise=True)
    def decrypt(self, ciphertext: str) -> str:
        try:
            response: dict[str, Any] = self.client.secrets.transit.decrypt_data(
                name=self.settings.vault_transit_key,
                ciphertext=ciphertext,
            )
            plaintext_b64 = response['data']['plaintext']
            return base64.b64decode(plaintext_b64).decode('utf-8')
        except Exception as exc:
            logger.exception('vault_decrypt_failed')
            raise VaultDecryptError('No se pudo descifrar el contenido recibido') from exc

    def decrypt_json(self, ciphertext: str) -> dict[str, Any]:
        return json.loads(self.decrypt(ciphertext))
