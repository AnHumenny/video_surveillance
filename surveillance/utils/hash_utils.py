import hashlib


def hash_password(password: str) -> str:
    """hashing password."""
    return hashlib.sha256(password.encode()).hexdigest()  # добавить соль
