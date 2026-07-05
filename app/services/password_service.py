from __future__ import annotations

import hashlib
import hmac
import secrets

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
TOKEN_BYTES = 32


def hash_password(password: str) -> tuple[str, str, str]:
    salt = secrets.token_hex(16)
    password_hash = _derive_password_hash(password, salt, PASSWORD_ITERATIONS)
    algorithm = f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}"
    return password_hash, salt, algorithm


def verify_password(
    password: str,
    *,
    password_hash: str,
    password_salt: str,
    password_algorithm: str,
) -> bool:
    try:
        algorithm, iterations_text = password_algorithm.split("$", 1)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if algorithm != PASSWORD_ALGORITHM:
        return False
    candidate = _derive_password_hash(password, password_salt, iterations)
    return hmac.compare_digest(candidate, password_hash)


def generate_auth_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_auth_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _derive_password_hash(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()
