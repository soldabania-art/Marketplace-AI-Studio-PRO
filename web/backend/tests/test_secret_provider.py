from cryptography.fernet import Fernet
import pytest

from app.secret_provider import FernetSecretProvider, SecretProviderError


def test_fernet_provider_round_trip_without_plaintext_ciphertext():
    provider = FernetSecretProvider(Fernet.generate_key().decode())
    secret = 'wb-super-secret-token-123456789'
    encrypted = provider.encrypt(secret)
    assert secret not in encrypted
    assert provider.decrypt(encrypted) == secret


def test_fernet_provider_rejects_wrong_key():
    first = FernetSecretProvider(Fernet.generate_key().decode())
    second = FernetSecretProvider(Fernet.generate_key().decode())
    encrypted = first.encrypt('wb-secret-token-123456789')
    with pytest.raises(SecretProviderError):
        second.decrypt(encrypted)
