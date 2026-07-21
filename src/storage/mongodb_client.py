"""
mongodb_client.py

O que é este arquivo:
Centraliza a conexão com o MongoDB, para que nenhum outro script precise
saber os detalhes de "como conectar" - eles só chamam get_database() e
pronto. Isso evita repetir a mesma lógica de conexão em vários lugares.
"""

import os
from pymongo import MongoClient
from pymongo.database import Database
from dotenv import load_dotenv

load_dotenv()

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Retorna um cliente MongoDB único (reaproveitado entre chamadas)."""
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI", "mongodb://ecomonitor:ecomonitor123@localhost:27017")
        _client = MongoClient(uri)
    return _client


def get_database() -> Database:
    """Retorna o objeto do banco 'ecomonitor', pronto para acessar coleções."""
    db_name = os.getenv("MONGO_DB_NAME", "ecomonitor")
    return get_client()[db_name]


def check_mongodb_connection() -> bool:
    """Verifica se a conexão com o MongoDB está ativa e respondendo."""
    try:
        client = get_client()
        client.admin.command('ping', serverSelectionTimeoutMS=2000)
        return True
    except Exception:
        return False


def ensure_indexes() -> None:
    """
    Cria os índices usados pelas consultas mais frequentes do sistema.

    O que é um índice, na prática: uma estrutura auxiliar que faz o MongoDB
    encontrar documentos rapidamente em vez de varrer a coleção inteira.
    Aqui criamos índices nos campos que mais aparecem em filtros ($match)
    e agregações, conforme descrito em docs/aggregation_model.md.
    """
    db = get_database()

    # Acelera a busca de eventos por setor (usado no ranking de anomalias)
    db.events.create_index("sector_id")

    # Acelera a busca de eventos com notificação pendente
    # (usado na tela principal do Streamlit e no alerta ao gestor)
    db.events.create_index("notification.status")

    print("Índices criados/confirmados em 'events.sector_id' e 'events.notification.status'.")


if __name__ == "__main__":
    # Executar este arquivo diretamente testa a conexão e cria os índices.
    database = get_database()
    print(f"Conectado ao banco: {database.name}")
    ensure_indexes()
