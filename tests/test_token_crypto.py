import pytest
from cryptography.fernet import Fernet

from app.security.token_crypto import TokenCrypto, TokenCryptoError


def test_encrypt_decrypt_round_trip() -> None:
    crypto = TokenCrypto(Fernet.generate_key().decode())
    encrypted = crypto.encrypt("secret-token")

    assert encrypted != "secret-token"
    assert crypto.decrypt(encrypted) == "secret-token"


def test_invalid_key_is_rejected() -> None:
    with pytest.raises(TokenCryptoError):
        TokenCrypto("invalid")
