"""
neo4j_ecomonitor.py — EcoMonitor · Neo4j + GDS Degree Centrality

Cria no Neo4j um grafo baseado nos dados já existentes no MongoDB.

Nós:
  Building, Sector, Sensor e Event

Relacionamentos:
  (Building)-[:POSSUI]->(Sector)
  (Sector)-[:MONITORADO_POR]->(Sensor)
  (Sector)-[:GEROU]->(Event)

Operação GDS:
  Degree Centrality nos setores. Quanto mais eventos de anomalia um setor
  gerou, maior sua centralidade e maior sua prioridade de manutenção.

Antes de executar:
  1. Configure MongoDB e Neo4j no arquivo .env
  2. Rode: python src/storage/simulator.py
  3. Rode: python neo4j_ecomonitor.py
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from src.storage.mongodb_client import get_database

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def separador(titulo: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {titulo}")
    print("=" * 72)


def sub(titulo: str) -> None:
    print(f"\n── {titulo} ──")


def normalizar_data(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def carregar_dados_mongodb() -> tuple[list[dict], list[dict], list[dict]]:
    db = get_database()
    buildings = list(db.buildings.find())
    sectors = list(db.sectors.find())
    events = list(db.events.find({"event_type": "HIGH_CONSUMPTION"}))
    return buildings, sectors, events


class EcoMonitorGraph:
    def __init__(self) -> None:
        if not NEO4J_PASSWORD:
            raise ValueError("Defina NEO4J_PASSWORD no arquivo .env.")
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )

    def close(self) -> None:
        self.driver.close()

    def run(self, query: str, params: dict | None = None) -> list[Any]:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            return list(session.run(query, params or {}))

    def testar_conexao(self) -> None:
        self.driver.verify_connectivity()

    def limpar_grafo(self) -> None:
        self.run("MATCH (n) DETACH DELETE n")

    def criar_constraints(self) -> None:
        constraints = [
            "CREATE CONSTRAINT building_id IF NOT EXISTS FOR (n:Building) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT sensor_id IF NOT EXISTS FOR (n:Sensor) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE",
        ]
        for query in constraints:
            self.run(query)

    def importar_dados(
        self,
        buildings: list[dict],
        sectors: list[dict],
        events: list[dict],
    ) -> None:
        for building in buildings:
            self.run(
                """
                MERGE (b:Building {id: $id})
                SET b.name = $name,
                    b.address = $address,
                    b.status = $status
                """,
                {
                    "id": str(building["_id"]),
                    "name": building.get("name", ""),
                    "address": building.get("address", ""),
                    "status": building.get("status", ""),
                },
            )

        for sector in sectors:
            params = {
                "id": str(sector["_id"]),
                "building_id": str(sector["building_id"]),
                "name": sector.get("name", ""),
                "threshold": float(sector.get("threshold_kwh", 0)),
                "status": sector.get("status", ""),
                "sensor_id": str(sector.get("sensor_id", "sem_sensor")),
            }
            self.run(
                """
                MERGE (s:Sector {id: $id})
                SET s.name = $name,
                    s.threshold_kwh = $threshold,
                    s.status = $status
                WITH s
                MATCH (b:Building {id: $building_id})
                MERGE (b)-[:POSSUI]->(s)
                WITH s
                MERGE (sensor:Sensor {id: $sensor_id})
                MERGE (s)-[:MONITORADO_POR]->(sensor)
                """,
                params,
            )

        for event in events:
            self.run(
                """
                MATCH (s:Sector {id: $sector_id})
                MERGE (e:Event {id: $id})
                SET e.type = $type,
                    e.value_kwh = $value,
                    e.threshold_kwh = $threshold,
                    e.status = $status,
                    e.detected_at = $detected_at
                MERGE (s)-[:GEROU]->(e)
                """,
                {
                    "id": str(event["_id"]),
                    "sector_id": str(event["sector_id"]),
                    "type": event.get("event_type", ""),
                    "value": float(event.get("value_kwh", 0)),
                    "threshold": float(event.get("threshold_kwh", 0)),
                    "status": event.get("notification", {}).get("status", ""),
                    "detected_at": normalizar_data(event.get("detected_at")),
                },
            )

    def consultas_basicas(self) -> None:
        sub("Setores e seus prédios")
        rows = self.run(
            """
            MATCH (b:Building)-[:POSSUI]->(s:Sector)
            RETURN b.name AS building, s.name AS sector,
                   s.threshold_kwh AS threshold
            ORDER BY s.name
            """
        )
        for row in rows:
            print(
                f"  🏢 {row['building']} → {row['sector']} "
                f"(limite {row['threshold']} kWh)"
            )

        sub("Quantidade de anomalias por setor")
        rows = self.run(
            """
            MATCH (s:Sector)-[:GEROU]->(e:Event)
            RETURN s.id AS sector_id, s.name AS sector,
                   count(e) AS total_events,
                   round(avg(e.value_kwh), 2) AS avg_consumption
            ORDER BY total_events DESC
            """
        )
        for row in rows:
            print(
                f"  ⚡ {row['sector']}: {row['total_events']} evento(s), "
                f"média {row['avg_consumption']} kWh"
            )

    def executar_degree_centrality(self) -> None:
        separador("ETAPA 3 — GDS Degree Centrality")
        print(
            "\n  A centralidade de grau mede quantas conexões cada setor possui.\n"
            "  Neste grafo, cada conexão GEROU representa um evento anômalo.\n"
            "  Portanto, o setor com maior score é o mais crítico para manutenção."
        )

        try:
            versao = self.run("RETURN gds.version() AS version")[0]["version"]
            print(f"\n  ✅ GDS disponível. Versão: {versao}")

            try:
                self.run("CALL gds.graph.drop('ecomonitor-grafo', false)")
            except Neo4jError:
                pass

            self.run(
                """
                CALL gds.graph.project(
                    'ecomonitor-grafo',
                    ['Sector', 'Event'],
                    {GEROU: {orientation: 'UNDIRECTED'}}
                )
                """
            )

            rows = self.run(
                """
                CALL gds.degree.stream('ecomonitor-grafo')
                YIELD nodeId, score
                WITH gds.util.asNode(nodeId) AS node, score
                WHERE node:Sector
                SET node.degree_score = score
                RETURN node.id AS sector_id,
                       node.name AS sector,
                       score
                ORDER BY score DESC
                """
            )

            print("\n  Ranking GDS de setores críticos:")
            for posicao, row in enumerate(rows, start=1):
                print(
                    f"  #{posicao} {row['sector']}: "
                    f"score {int(row['score'])}"
                )

            self.run("CALL gds.graph.drop('ecomonitor-grafo')")

        except Neo4jError as exc:
            print(f"\n  ⚠️ GDS não pôde ser executado: {exc.code or str(exc)}")
            print("  Executando a mesma lógica com Cypher puro como alternativa.")

            rows = self.run(
                """
                MATCH (s:Sector)
                OPTIONAL MATCH (s)-[:GEROU]->(e:Event)
                WITH s, count(e) AS degree_score
                SET s.degree_score = degree_score
                RETURN s.id AS sector_id,
                       s.name AS sector,
                       degree_score AS score
                ORDER BY score DESC
                """
            )

            for posicao, row in enumerate(rows, start=1):
                print(
                    f"  #{posicao} {row['sector']}: "
                    f"score {int(row['score'])}"
                )

    def mostrar_resumo(self) -> None:
        separador("ETAPA 4 — Resumo do grafo")
        nos = self.run(
            "MATCH (n) RETURN labels(n)[0] AS type, count(*) AS total ORDER BY type"
        )
        rels = self.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS total ORDER BY type"
        )

        print("\n  Nós:")
        for row in nos:
            print(f"    {row['type']:<15} {row['total']}")

        print("\n  Relacionamentos:")
        for row in rels:
            print(f"    {row['type']:<20} {row['total']}")


def executar() -> None:
    buildings, sectors, events = carregar_dados_mongodb()

    if not buildings or not sectors:
        raise SystemExit(
            "MongoDB sem dados. Rode primeiro: python src/storage/simulator.py"
        )

    separador("ETAPA 1 — Conectando e criando o grafo EcoMonitor")
    print(
        f"  Dados encontrados no MongoDB: {len(buildings)} prédio(s), "
        f"{len(sectors)} setor(es) e {len(events)} evento(s)."
    )

    graph = EcoMonitorGraph()
    try:
        graph.testar_conexao()
        print("  ✅ Conexão com Neo4j realizada.")

        sub("Limpando grafo anterior")
        graph.limpar_grafo()
        graph.criar_constraints()
        print("  ✅ Grafo limpo e constraints criadas.")

        sub("Importando dados do MongoDB")
        graph.importar_dados(buildings, sectors, events)
        print("  ✅ Nós e relacionamentos criados.")

        separador("ETAPA 2 — Consultas Cypher")
        graph.consultas_basicas()
        graph.executar_degree_centrality()
        graph.mostrar_resumo()

    except Neo4jError as exc:
        raise SystemExit(f"Erro no Neo4j: {exc}") from exc
    finally:
        graph.close()

    print("\n✅ Grafo EcoMonitor criado e analisado com sucesso.\n")


if __name__ == "__main__":
    executar()
