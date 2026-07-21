"""
redis_client.py

Centraliza a conexão com o Redis, seguindo a mesma ideia do mongodb_client.py.
As credenciais são lidas do arquivo .env.
"""

import os

import redis
from dotenv import load_dotenv
from redis import Redis

load_dotenv()

_client: Redis | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def get_redis() -> Redis:
    """Retorna uma conexão Redis única e reutilizável."""
    global _client

    if _client is None:
        password = os.getenv("REDIS_PASSWORD") or None
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            username=os.getenv("REDIS_USERNAME") or None,
            password=password,
            ssl=_env_bool("REDIS_SSL", False),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    return _client


def test_connection() -> None:
    """Testa a conexão e gera um erro claro caso o Redis não responda."""
    client = get_redis()
    if not client.ping():
        raise ConnectionError("O Redis não respondeu ao comando PING.")


def check_redis_connection() -> bool:
    """Verifica se a conexão com o Redis está ativa e respondendo."""
    try:
        test_connection()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    test_connection()
    print("Conexão com o Redis realizada com sucesso.")
