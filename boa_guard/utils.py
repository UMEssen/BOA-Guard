import hashlib
import secrets


def generate_hash(nbytes: int = 32) -> str:
    random_bytes = secrets.token_bytes(nbytes)
    return hashlib.sha256(random_bytes).hexdigest()
