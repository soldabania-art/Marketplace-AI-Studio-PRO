"""Secret envelope abstraction for marketplace credentials.

Fernet is the migration-compatible provider for the first deployment. Production
KMS/Vault providers can implement the same interface without changing callers or
persisting plaintext credentials.
"""
from abc import ABC, abstractmethod

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


class SecretProviderError(RuntimeError):
    pass


class SecretProvider(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...


class FernetSecretProvider(SecretProvider):
    def __init__(self, key: str):
        if not key:
            raise SecretProviderError('Marketplace encryption key is not configured')
        try:
            self._fernet = Fernet(key.encode())
        except Exception as exc:
            raise SecretProviderError('Marketplace encryption key is invalid') from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise SecretProviderError('Marketplace credential cannot be decrypted') from exc


def get_secret_provider() -> SecretProvider:
    settings = get_settings()
    provider = settings.marketplace_secret_provider.strip().lower()
    if provider == 'fernet':
        return FernetSecretProvider(settings.marketplace_token_key)
    # Fail closed: an unsupported provider must never silently fall back to a
    # weaker local key in production.
    raise SecretProviderError(f'Unsupported marketplace secret provider: {provider}')
