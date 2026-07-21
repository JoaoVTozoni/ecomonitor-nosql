"""
redis_funcionalidades.py — EcoMonitor · Redis

Mantém a mesma organização usada no projeto CineHub, mas com funcionalidades
ligadas ao monitoramento de consumo de energia.

FUNCIONALIDADE 1 — Login e sessão do gestor
  HASH: dados do gestor
  STRING com TTL: token de sessão
  SET: sessões ativas

FUNCIONALIDADE 2 — Processamento de alertas
  STRING com TTL: cache dos alertas pendentes
  Bloom Filter: evita colocar o mesmo evento duas vezes na fila
  HyperLogLog: estima quantos setores únicos geraram anomalias
  STREAM: fila de alertas para notificação
  ZSET: ranking de setores por quantidade de anomalias

Antes de executar:
  1. Configure MongoDB e Redis no arquivo .env
  2. Rode: python src/storage/simulator.py
  3. Rode: python redis_funcionalidades.py
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from typing import Any

from redis import Redis
from redis.exceptions import RedisError, ResponseError

from src.storage.mongodb_client import get_database
from src.storage.redis_client import get_redis, test_connection

PREFIXO = "ecomonitor"
CACHE_TTL_SEGUNDOS = 60
SESSAO_TTL_SEGUNDOS = 600


def separador(titulo: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {titulo}")
    print("=" * 72)


def sub(titulo: str) -> None:
    print(f"\n── {titulo} ──")


def hash_senha(senha: str) -> str:
    """Hash simples para demonstração acadêmica."""
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


def limpar_chaves_demo(r: Redis) -> None:
    """Remove apenas as chaves do EcoMonitor, sem apagar outros projetos."""
    chaves = list(r.scan_iter(match=f"{PREFIXO}:*"))
    if chaves:
        r.delete(*chaves)
    print(f"  Banco Redis preparado: {len(chaves)} chave(s) antiga(s) removida(s).")


# =============================================================================
# FUNCIONALIDADE 1 — LOGIN E SESSÃO DO GESTOR
# =============================================================================


def cadastrar_gestor(r: Redis) -> str:
    chave = f"{PREFIXO}:gestor:admin"
    r.hset(
        chave,
        mapping={
            "nome": "Gestor EcoMonitor",
            "email": "gestor@ecomonitor.com",
            "senha_hash": hash_senha("eco123"),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    return chave


def fazer_login(
    r: Redis,
    gestor_id: str,
    senha_digitada: str,
    ttl_segundos: int = SESSAO_TTL_SEGUNDOS,
) -> str | None:
    senha_salva = r.hget(gestor_id, "senha_hash")

    if not senha_salva:
        print("  ❌ Gestor não encontrado.")
        return None

    if senha_salva != hash_senha(senha_digitada):
        print("  ❌ Senha incorreta.")
        return None

    token = secrets.token_hex(16)
    chave_sessao = f"{PREFIXO}:sessao:{token}"

    r.setex(chave_sessao, ttl_segundos, gestor_id)
    r.sadd(f"{PREFIXO}:sessoes:ativas", token)

    nome = r.hget(gestor_id, "nome")
    print(f"  ✅ Login realizado para {nome}.")
    print(f"     Token: {token}")
    print(f"     TTL: {r.ttl(chave_sessao)} segundos")
    return token


def verificar_sessao(r: Redis, token: str) -> bool:
    chave_sessao = f"{PREFIXO}:sessao:{token}"
    gestor_id = r.get(chave_sessao)

    if not gestor_id:
        r.srem(f"{PREFIXO}:sessoes:ativas", token)
        print("  ❌ Sessão inexistente ou expirada.")
        return False

    nome = r.hget(gestor_id, "nome")
    print(f"  ✅ Sessão válida para {nome}. TTL: {r.ttl(chave_sessao)} segundos.")
    return True


def fazer_logout(r: Redis, token: str) -> None:
    r.delete(f"{PREFIXO}:sessao:{token}")
    r.srem(f"{PREFIXO}:sessoes:ativas", token)
    print("  ✅ Logout realizado. Token removido.")


# =============================================================================
# FUNCIONALIDADE 2 — CACHE, BLOOM FILTER, HLL, STREAM E ZSET
# =============================================================================


def _serializar(documento: dict[str, Any]) -> dict[str, Any]:
    """Converte tipos do MongoDB, como datetime, para valores serializáveis."""
    return json.loads(json.dumps(documento, default=str))


def consultar_alertas_pendentes_mongodb(limite: int = 10) -> list[dict[str, Any]]:
    db = get_database()
    pipeline = [
        {"$match": {"notification.status": "PENDING"}},
        {
            "$lookup": {
                "from": "sectors",
                "localField": "sector_id",
                "foreignField": "_id",
                "as": "sector_info",
            }
        },
        {"$unwind": "$sector_info"},
        {
            "$lookup": {
                "from": "buildings",
                "localField": "building_id",
                "foreignField": "_id",
                "as": "building_info",
            }
        },
        {"$unwind": "$building_info"},
        {"$sort": {"value_kwh": -1}},
        {"$limit": limite},
        {
            "$project": {
                "_id": 1,
                "sector_id": 1,
                "sensor_id": "$sector_info.sensor_id",
                "sector_name": "$sector_info.name",
                "building_name": "$building_info.name",
                "event_type": 1,
                "value_kwh": 1,
                "threshold_kwh": 1,
                "detected_at": 1,
            }
        },
    ]
    return [_serializar(item) for item in db.events.aggregate(pipeline)]


def buscar_alertas_com_cache(r: Redis) -> tuple[list[dict[str, Any]], str]:
    chave_cache = f"{PREFIXO}:cache:alertas:pendentes"
    valor_cache = r.get(chave_cache)

    if valor_cache:
        return json.loads(valor_cache), "HIT"

    alertas = consultar_alertas_pendentes_mongodb()
    r.setex(chave_cache, CACHE_TTL_SEGUNDOS, json.dumps(alertas, ensure_ascii=False))
    return alertas, "MISS"


def bloom_disponivel(r: Redis) -> bool:
    """Verifica se o Redis possui o módulo RedisBloom."""
    chave_teste = f"{PREFIXO}:bloom:teste"
    try:
        r.execute_command("BF.ADD", chave_teste, "teste")
        r.delete(chave_teste)
        return True
    except ResponseError:
        return False


def evento_ja_processado(r: Redis, evento_id: str, usar_bloom: bool) -> bool:
    if usar_bloom:
        return bool(
            r.execute_command(
                "BF.EXISTS", f"{PREFIXO}:bloom:alertas_processados", evento_id
            )
        )
    return bool(r.sismember(f"{PREFIXO}:fallback:alertas_processados", evento_id))


def registrar_evento_processado(r: Redis, evento_id: str, usar_bloom: bool) -> None:
    if usar_bloom:
        r.execute_command(
            "BF.ADD", f"{PREFIXO}:bloom:alertas_processados", evento_id
        )
    else:
        r.sadd(f"{PREFIXO}:fallback:alertas_processados", evento_id)


def enviar_alertas_para_stream(
    r: Redis,
    alertas: list[dict[str, Any]],
    usar_bloom: bool,
) -> tuple[int, int]:
    enviados = 0
    ignorados = 0

    for alerta in alertas:
        evento_id = str(alerta["_id"])
        setor_id = str(alerta["sector_id"])

        if evento_ja_processado(r, evento_id, usar_bloom):
            ignorados += 1
            continue

        mensagem = (
            f"Alerta em {alerta['building_name']} / {alerta['sector_name']}: "
            f"{alerta['value_kwh']} kWh, limite {alerta['threshold_kwh']} kWh."
        )

        r.xadd(
            f"{PREFIXO}:stream:alertas",
            {
                "event_id": evento_id,
                "sector_id": setor_id,
                "sensor_id": str(alerta.get("sensor_id", "")),
                "message": mensagem,
                "detected_at": str(alerta["detected_at"]),
            },
            maxlen=1000,
            approximate=True,
        )

        # HLL: conta setores únicos com anomalia.
        r.pfadd(f"{PREFIXO}:hll:setores_com_anomalia", setor_id)

        # ZSET: cria um ranking simples pela quantidade de eventos.
        r.zincrby(f"{PREFIXO}:ranking:setores", 1, setor_id)

        registrar_evento_processado(r, evento_id, usar_bloom)
        enviados += 1

    return enviados, ignorados


def mostrar_ultimas_mensagens(r: Redis, quantidade: int = 5) -> None:
    mensagens = r.xrevrange(
        f"{PREFIXO}:stream:alertas", max="+", min="-", count=quantidade
    )
    if not mensagens:
        print("  Nenhuma mensagem disponível no Stream.")
        return

    for message_id, campos in mensagens:
        print(f"  {message_id} → {campos['message']}")


def executar() -> None:
    r = get_redis()

    separador("CONEXÃO")
    try:
        test_connection()
        print("  ✅ Redis conectado.")
    except RedisError as exc:
        raise SystemExit(f"  ❌ Não foi possível conectar ao Redis: {exc}") from exc

    resetar = os.getenv("RESET_REDIS_DEMO", "true").lower() in {
        "1",
        "true",
        "yes",
        "sim",
        "on",
    }
    if resetar:
        limpar_chaves_demo(r)

    separador("FUNCIONALIDADE 1 — Login e sessão do gestor")
    gestor_id = cadastrar_gestor(r)
    print(f"  ✅ Gestor cadastrado em HASH: {gestor_id}")

    sub("Tentativa com senha correta")
    token = fazer_login(r, gestor_id, "eco123")

    sub("Tentativa com senha incorreta")
    fazer_login(r, gestor_id, "senha_errada")

    if token:
        sub("Verificação da sessão")
        verificar_sessao(r, token)
        print(
            f"  Sessões ativas no SET: "
            f"{r.scard(f'{PREFIXO}:sessoes:ativas')}"
        )

    separador("FUNCIONALIDADE 2 — Alertas, cache e mensageria")

    sub("Primeira consulta: cache MISS")
    alertas, status_cache = buscar_alertas_com_cache(r)
    print(f"  Cache: {status_cache}. Alertas encontrados: {len(alertas)}")

    sub("Segunda consulta: cache HIT")
    _, status_cache = buscar_alertas_com_cache(r)
    print(
        f"  Cache: {status_cache}. "
        f"TTL restante: {r.ttl(f'{PREFIXO}:cache:alertas:pendentes')} segundos"
    )

    if not alertas:
        print(
            "\n  ⚠️ Nenhum alerta pendente encontrado no MongoDB.\n"
            "     Rode primeiro: python src/storage/simulator.py"
        )
    else:
        usar_bloom = bloom_disponivel(r)
        modo = "Bloom Filter" if usar_bloom else "SET de fallback"
        print(f"\n  Estrutura para deduplicação: {modo}")
        if not usar_bloom:
            print(
                "  ⚠️ O Redis atual não possui RedisBloom. O script continua funcionando,\n"
                "     mas para demonstrar BF.ADD/BF.EXISTS use Redis Stack ou Redis Cloud."
            )

        sub("Envio dos alertas para o Redis Stream")
        enviados, ignorados = enviar_alertas_para_stream(r, alertas, usar_bloom)
        print(f"  ✅ {enviados} alerta(s) enviado(s) ao Stream.")
        print(f"  ♻️ {ignorados} alerta(s) duplicado(s) ignorado(s).")

        # Executa outra vez para demonstrar a deduplicação.
        enviados_2, ignorados_2 = enviar_alertas_para_stream(r, alertas, usar_bloom)
        print(
            f"  Segunda tentativa: {enviados_2} novo(s), "
            f"{ignorados_2} duplicado(s) bloqueado(s)."
        )

        sub("Últimas mensagens da fila")
        mostrar_ultimas_mensagens(r)

        sub("HyperLogLog e ranking ZSET")
        total_setores = r.pfcount(f"{PREFIXO}:hll:setores_com_anomalia")
        print(f"  Setores únicos com anomalia (HLL): {total_setores}")

        ranking = r.zrevrange(
            f"{PREFIXO}:ranking:setores", 0, -1, withscores=True
        )
        for posicao, (setor_id, pontuacao) in enumerate(ranking, start=1):
            print(f"  #{posicao} {setor_id}: {int(pontuacao)} evento(s)")

    if token:
        separador("LOGOUT")
        fazer_logout(r, token)

    separador("RESUMO DAS CHAVES REDIS")
    chaves = sorted(r.scan_iter(match=f"{PREFIXO}:*"))
    for chave in chaves:
        tipo = r.type(chave)
        ttl = r.ttl(chave)
        ttl_texto = f" | TTL: {ttl}s" if ttl >= 0 else ""
        print(f"  {chave:<55} {tipo}{ttl_texto}")

    print("\n✅ Funcionalidades Redis do EcoMonitor concluídas.\n")


if __name__ == "__main__":
    executar()
