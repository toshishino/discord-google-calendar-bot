from cryptography.fernet import Fernet, InvalidToken


class TokenCryptoError(ValueError):
    pass


class TokenCrypto:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise TokenCryptoError(
                "TOKEN_ENCRYPTION_KEY is not a valid Fernet key"
            ) from exc

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise TokenCryptoError("Stored token could not be decrypted") from exc
