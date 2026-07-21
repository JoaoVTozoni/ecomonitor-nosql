"""
aggregations.py

O que é este arquivo:
Implementa os 2 pipelines de agregação pedidos na Entrega 4, cada um
resolvendo uma pergunta distinta e sustentando a funcionalidade principal
do sistema (alertar o gestor sobre consumo anômalo a tempo).

Como rodar (com o venv ativado e o banco já populado pelo simulator.py):
    python3 src/storage/aggregations.py

O que é uma "pipeline de agregação"? É uma sequência de etapas que os
documentos atravessam, uma por uma, até virarem o resultado final. Cada
etapa recebe a saída da etapa anterior - por isso a ordem importa.
Abaixo, cada etapa tem um comentário explicando o que ela faz e por quê.
"""

from mongodb_client import get_database


def pipeline_1_ranking_setores_por_anomalia(db):
    """
    PERGUNTA QUE RESPONDE:
    "Quais setores mais geram eventos de consumo anômalo, e qual o consumo
    médio desses eventos?" - ajuda o gestor a decidir onde investir em
    manutenção elétrica (setores com muitos alertas podem ter um problema
    estrutural, não só picos pontuais).

    OPERADORES USADOS: $match, $group, $sort, $lookup, $unwind, $set,
    $project, $merge.
    """
    pipeline = [
        # 1. $match: filtra só os eventos do tipo que realmente importa
        #    para este relatório (consumo acima do limite).
        {"$match": {"event_type": "HIGH_CONSUMPTION"}},

        # 2. $group: agrupa os eventos por setor, contando quantos eventos
        #    cada setor teve e calculando a média de consumo entre eles.
        {
            "$group": {
                "_id": "$sector_id",
                "total_events": {"$sum": 1},
                "avg_consumption_kwh": {"$avg": "$value_kwh"},
                "max_consumption_kwh": {"$max": "$value_kwh"},
            }
        },

        # 3. $sort: ordena do setor com mais eventos para o com menos,
        #    já que o objetivo é identificar os setores mais problemáticos.
        {"$sort": {"total_events": -1}},

        # 4. $lookup: como o $group só deixou o sector_id (agora em "_id"),
        #    buscamos na coleção "sectors" o nome e o prédio associado.
        {
            "$lookup": {
                "from": "sectors",
                "localField": "_id",
                "foreignField": "_id",
                "as": "sector_info",
            }
        },
        # $lookup sempre retorna uma lista (mesmo com 1 resultado);
        # $unwind "desempacota" essa lista em um objeto único.
        {"$unwind": "$sector_info"},

        # 5. $lookup + $unwind de novo: agora buscamos o nome do prédio,
        #    usando o building_id que veio dentro de sector_info.
        {
            "$lookup": {
                "from": "buildings",
                "localField": "sector_info.building_id",
                "foreignField": "_id",
                "as": "building_info",
            }
        },
        {"$unwind": "$building_info"},

        # 6. $set: cria um campo calculado ("severity") a partir dos dados
        #    já agregados - não existia nos documentos originais.
        {
            "$set": {
                "severity": {
                    "$cond": {
                        "if": {"$gte": ["$total_events", 5]},
                        "then": "ALTA",
                        "else": "MODERADA",
                    }
                }
            }
        },

        # 7. $project: seleciona só os campos relevantes para o relatório
        #    final, renomeando para nomes mais claros. Mantemos o _id igual
        #    ao sector_id (em vez de removê-lo) para que o $merge, mais
        #    abaixo, saiba identificar corretamente o mesmo setor entre uma
        #    execução e outra - sem isso, cada execução criaria uma linha
        #    nova em vez de atualizar a existente.
        {
            "$project": {
                "_id": "$_id",
                "sector_id": "$_id",
                "sector_name": "$sector_info.name",
                "building_name": "$building_info.name",
                "total_events": 1,
                "avg_consumption_kwh": {"$round": ["$avg_consumption_kwh", 2]},
                "max_consumption_kwh": 1,
                "severity": 1,
            }
        },

        # 8. $merge: grava o resultado numa coleção separada
        #    ("reports_sector_ranking"), sobrescrevendo o conteúdo anterior.
        #    Isso permite que outra tela (ou o gestor) consulte o relatório
        #    já pronto, sem precisar rodar a agregação de novo toda vez.
        {
            "$merge": {
                "into": "reports_sector_ranking",
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        },
    ]

    db.events.aggregate(pipeline)

    # Como o $merge não retorna os documentos diretamente, buscamos na
    # coleção de destino para exibir o resultado.
    result = list(db.reports_sector_ranking.find().sort("total_events", -1))
    return result


def pipeline_2_amostra_alertas_pendentes(db):
    """
    PERGUNTA QUE RESPONDE:
    "Me dê uma amostra de alertas pendentes, prontos com todos os dados
    para simular o envio de notificação ao gestor." - é essa consulta que
    alimentaria, no mundo real, um job que dispara e-mails/WhatsApp.

    OPERADORES USADOS: $match, $sample, $lookup, $unwind, $set, $project,
    $sort, $merge.
    """
    # Como o $sample sorteia documentos diferentes a cada execução, limpamos
    # a coleção de destino antes de gravar a nova amostra - caso contrário,
    # o $merge iria apenas somar mais 5 documentos por cima dos anteriores,
    # já que cada evento tem um _id diferente e nunca "bate" com o anterior.
    db.reports_notification_queue.delete_many({})

    pipeline = [
        # 1. $match: só eventos que ainda não foram notificados.
        {"$match": {"notification.status": "PENDING"}},

        # 2. $sample: em vez de pegar todos, pegamos uma amostra aleatória
        #    de até 5 documentos - útil para simular um lote de envio sem
        #    sobrecarregar o "canal de notificação" de uma vez só.
        {"$sample": {"size": 5}},

        # 3. e 4. $lookup + $unwind: trazem o nome do setor.
        {
            "$lookup": {
                "from": "sectors",
                "localField": "sector_id",
                "foreignField": "_id",
                "as": "sector_info",
            }
        },
        {"$unwind": "$sector_info"},

        # 5. e 6. $lookup + $unwind: trazem o nome do prédio.
        {
            "$lookup": {
                "from": "buildings",
                "localField": "building_id",
                "foreignField": "_id",
                "as": "building_info",
            }
        },
        {"$unwind": "$building_info"},

        # 7. $set: monta a mensagem de alerta pronta para "envio",
        #    concatenando os dados já cruzados.
        {
            "$set": {
                "alert_message": {
                    "$concat": [
                        "Alerta no setor ",
                        "$sector_info.name",
                        " (",
                        "$building_info.name",
                        "): consumo de ",
                        {"$toString": "$value_kwh"},
                        " kWh, acima do limite de ",
                        {"$toString": "$threshold_kwh"},
                        " kWh.",
                    ]
                }
            }
        },

        # 8. $project: seleciona os campos finais do "pacote de notificação".
        {
            "$project": {
                "_id": 1,
                "sector_name": "$sector_info.name",
                "building_name": "$building_info.name",
                "value_kwh": 1,
                "threshold_kwh": 1,
                "detected_at": 1,
                "alert_message": 1,
            }
        },

        # 9. $sort: prioriza notificar primeiro quem consumiu mais acima
        #    do limite.
        {"$sort": {"value_kwh": -1}},

        # 10. $merge: grava a fila de notificação pronta numa coleção
        #     separada, que representaria a "fila de envio" do sistema.
        {
            "$merge": {
                "into": "reports_notification_queue",
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        },
    ]

    db.events.aggregate(pipeline)

    result = list(db.reports_notification_queue.find().sort("value_kwh", -1))
    return result


def main():
    db = get_database()

    print("=" * 70)
    print("PIPELINE 1 — Ranking de setores por eventos de consumo anômalo")
    print("=" * 70)
    ranking = pipeline_1_ranking_setores_por_anomalia(db)
    if not ranking:
        print("Nenhum resultado. Rode 'python3 src/storage/simulator.py' antes.")
    for r in ranking:
        print(
            f"- {r['building_name']} / {r['sector_name']}: "
            f"{r['total_events']} evento(s), "
            f"média {r['avg_consumption_kwh']} kWh, "
            f"pico {r['max_consumption_kwh']} kWh, "
            f"severidade {r['severity']}"
        )

    print()
    print("=" * 70)
    print("PIPELINE 2 — Amostra de alertas pendentes para notificação")
    print("=" * 70)
    sample = pipeline_2_amostra_alertas_pendentes(db)
    if not sample:
        print("Nenhum alerta pendente encontrado no momento.")
    for s in sample:
        print(f"- {s['alert_message']}")

    print()
    print("Resultados também gravados nas coleções:")
    print("  - reports_sector_ranking")
    print("  - reports_notification_queue")


if __name__ == "__main__":
    main()
