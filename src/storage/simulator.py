"""
simulator.py

O que é este arquivo:
Como não temos sensores de energia reais, este script "finge" ser os
sensores: cria prédios e setores fictícios, e gera leituras de consumo
periódicas para cada setor, ao longo de um dia. Sempre que uma leitura
ultrapassa o limite (threshold) do setor, um documento de EVENTO é criado
automaticamente - exatamente como aconteceria no sistema real.

Como rodar:
    python3 src/storage/simulator.py
"""

import random
from datetime import datetime, timedelta

from mongodb_client import get_database


def clear_previous_demo_data(db) -> None:
    """Remove dados de uma execução anterior do simulador, para começar limpo."""
    for collection_name in ["buildings", "sectors", "sessions", "readings", "events", "system_logs"]:
        db[collection_name].delete_many({})
    print("Base zerada. Gerando novos dados...")


def create_buildings_and_sectors(db):
    """Cria 1 prédio com 4 setores, cada um com um limite de consumo diferente."""
    building = {
        "_id": "bld_001",
        "name": "Edifício Aurora",
        "address": "Rua das Palmeiras, 123 - Araxá/MG",
        "total_sectors": 4,
        "status": "active",
        "created_at": datetime.utcnow(),
    }
    db.buildings.insert_one(building)

    sectors_config = [
        ("sec_001", "3º Andar - Ala Norte", "sensor_a17", 12.5),
        ("sec_002", "3º Andar - Ala Sul", "sensor_a18", 10.0),
        ("sec_003", "Garagem Subsolo", "sensor_b02", 20.0),
        ("sec_004", "Área Comum / Lazer", "sensor_c05", 8.0),
    ]

    sectors = []
    for sector_id, name, sensor_id, threshold in sectors_config:
        sector = {
            "_id": sector_id,
            "building_id": "bld_001",
            "name": name,
            "sensor_id": sensor_id,
            "threshold_kwh": threshold,
            "status": "online",
            "last_seen": datetime.utcnow(),
        }
        sectors.append(sector)

    db.sectors.insert_many(sectors)
    print(f"Criado 1 prédio e {len(sectors)} setores.")
    return sectors_config


def simulate_day(db, sectors_config, day_offset: int = 0):
    """
    Simula um dia inteiro de leituras (a cada 15 minutos = 96 leituras) para
    cada setor. Cada leitura tem uma chance pequena de ser um "pico" proposital,
    para garantir que eventos sejam gerados e o CRUD tenha o que demonstrar.
    """
    day = (datetime.utcnow() - timedelta(days=day_offset)).strftime("%Y-%m-%d")

    for sector_id, name, sensor_id, threshold in sectors_config:
        session_id = f"ses_{day.replace('-', '')}_{sector_id}"
        session_start = datetime.strptime(day, "%Y-%m-%d")

        session = {
            "_id": session_id,
            "sector_id": sector_id,
            "date": day,
            "started_at": session_start,
            "closed_at": session_start + timedelta(days=1),
            "total_consumption_kwh": 0.0,
            "status": "closed",
        }

        db.system_logs.insert_one({
            "_id": f"log_{session_id}_open",
            "type": "SESSION_OPENED",
            "sector_id": sector_id,
            "message": f"Sessão de monitoramento iniciada para o setor {name}",
            "timestamp": session_start,
        })

        total_consumption = 0.0
        readings = []
        events = []

        # 96 leituras = 1 a cada 15 minutos ao longo de 24h
        for i in range(96):
            timestamp = session_start + timedelta(minutes=15 * i)

            # Consumo normal simulado: variação aleatória em torno de 60% do threshold
            base_consumption = round(random.uniform(0.2, threshold * 0.6 / 4), 3)

            # 5% de chance de ser um pico anômalo (acima do threshold)
            is_spike = random.random() < 0.05
            if is_spike:
                consumption = round(threshold * random.uniform(1.1, 1.6), 3)
            else:
                consumption = base_consumption

            reading = {
                "_id": f"read_{session_id}_{i:03d}",
                "sector_id": sector_id,
                "session_id": session_id,
                "timestamp": timestamp,
                "consumption_kwh": consumption,
            }
            readings.append(reading)
            total_consumption += consumption

            if is_spike:
                event = {
                    "_id": f"evt_{session_id}_{i:03d}",
                    "sector_id": sector_id,
                    "session_id": session_id,
                    "building_id": "bld_001",
                    "event_type": "HIGH_CONSUMPTION",
                    "value_kwh": consumption,
                    "threshold_kwh": threshold,
                    "detected_at": timestamp,
                    "notification": {
                        "enabled": True,
                        "status": "PENDING",
                        "sent_at": None,
                    },
                    "demo": False,
                }
                events.append(event)

        session["total_consumption_kwh"] = round(total_consumption, 2)
        db.sessions.insert_one(session)
        db.readings.insert_many(readings)
        if events:
            db.events.insert_many(events)

        db.system_logs.insert_one({
            "_id": f"log_{session_id}_close",
            "type": "SESSION_CLOSED",
            "sector_id": sector_id,
            "message": f"Sessão encerrada. Consumo total: {session['total_consumption_kwh']} kWh. "
                       f"{len(events)} evento(s) de anomalia gerado(s).",
            "timestamp": session["closed_at"],
        })

        print(f"  - {name}: {len(readings)} leituras, {len(events)} evento(s) de anomalia.")


def main():
    db = get_database()
    clear_previous_demo_data(db)
    sectors_config = create_buildings_and_sectors(db)

    print("\nSimulando os últimos 3 dias de consumo...")
    for day_offset in range(2, -1, -1):  # 2 dias atrás, 1 dia atrás, hoje
        print(f"\nDia -{day_offset}:")
        simulate_day(db, sectors_config, day_offset=day_offset)

    print("\nSimulação concluída. Banco populado com sucesso.")
    print("Colecões geradas: buildings, sectors, sessions, readings, events, system_logs")


if __name__ == "__main__":
    main()
