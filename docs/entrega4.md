# Entrega 4 — Pipelines de Agregação e Índices

## Índices

Criados em `src/storage/mongodb_client.py` (função `ensure_indexes`), já executados desde a Entrega 3:

| Índice | Coleção.Campo | Por quê |
|---|---|---|
| 1 | `events.sector_id` | Acelera a busca de eventos de um setor específico — usado no Pipeline 1 (agrupar por setor) |
| 2 | `events.notification.status` | Acelera a busca de eventos com notificação pendente — usado no Pipeline 2 e na aba "Alertas" do Streamlit |

> **Por que um índice acelera a busca?** Sem índice, o MongoDB precisa olhar documento por documento (uma "varredura completa" da coleção) toda vez que alguém filtra por `sector_id` ou `notification.status`. Com o índice, ele mantém uma estrutura auxiliar ordenada só com esses campos, permitindo pular direto para os documentos relevantes — como o índice de um livro.

---

## Pipeline 1 — Ranking de setores por eventos de consumo anômalo

**Arquivo:** `src/storage/aggregations.py`, função `pipeline_1_ranking_setores_por_anomalia`

**Pergunta que responde:** "Quais setores mais geram eventos de consumo anômalo, e qual o consumo médio desses eventos?"

**Por que importa para a funcionalidade principal:** um setor que gera muitos alertas repetidamente pode indicar um problema estrutural (fiação antiga, equipamento com defeito), não apenas picos pontuais de uso. Esse relatório ajuda o gestor a decidir onde investir em manutenção, não só reagir alerta por alerta.

**Etapas da pipeline:**
1. `$match` — filtra só eventos do tipo `HIGH_CONSUMPTION`
2. `$group` — agrupa por setor, contando eventos e calculando média/pico de consumo
3. `$sort` — ordena do setor com mais eventos para o com menos
4. `$lookup` + `$unwind` — traz o nome do setor (coleção `sectors`)
5. `$lookup` + `$unwind` — traz o nome do prédio (coleção `buildings`)
6. `$set` — cria o campo calculado `severity` (ALTA/MODERADA) com base no total de eventos
7. `$project` — seleciona e renomeia os campos finais do relatório
8. `$merge` — grava o resultado na coleção `reports_sector_ranking`, para que outras telas possam consultar o relatório já pronto sem reprocessar

---

## Pipeline 2 — Amostra de alertas pendentes para notificação

**Arquivo:** `src/storage/aggregations.py`, função `pipeline_2_amostra_alertas_pendentes`

**Pergunta que responde:** "Me dê uma amostra de alertas pendentes, já prontos com a mensagem de notificação formatada."

**Por que importa para a funcionalidade principal:** representa exatamente o passo que, num sistema real, alimentaria um job de envio de e-mail/WhatsApp ao síndico — a agregação já entrega o "pacote pronto para notificar", não apenas dados brutos.

**Etapas da pipeline:**
1. `$match` — filtra só eventos com `notification.status: PENDING`
2. `$sample` — seleciona uma amostra aleatória de até 5 documentos (simula um lote de envio)
3. `$lookup` + `$unwind` — traz o nome do setor
4. `$lookup` + `$unwind` — traz o nome do prédio
5. `$set` — monta a string `alert_message`, concatenando os dados já cruzados
6. `$project` — seleciona os campos finais do "pacote de notificação"
7. `$sort` — prioriza notificar primeiro quem consumiu mais acima do limite
8. `$merge` — grava a fila pronta na coleção `reports_notification_queue`

---

## Como rodar e capturar as evidências

Com o ambiente já configurado (Docker rodando, venv ativado, banco populado pelo `simulator.py`):

```bash
python3 src/storage/aggregations.py
```

**Saída esperada** (os valores exatos variam, pois o simulador gera dados aleatórios):
```
======================================================================
PIPELINE 1 — Ranking de setores por eventos de consumo anômalo
======================================================================
- Edifício Aurora / 3º Andar - Ala Norte: 8 evento(s), média 15.32 kWh, pico 18.9 kWh, severidade ALTA
- Edifício Aurora / Área Comum / Lazer: 4 evento(s), média 10.87 kWh, pico 12.3 kWh, severidade MODERADA
...

======================================================================
PIPELINE 2 — Amostra de alertas pendentes para notificação
======================================================================
- Alerta no setor 3º Andar - Ala Norte (Edifício Aurora): consumo de 16.2 kWh, acima do limite de 12.5 kWh.
...

Resultados também gravados nas coleções:
  - reports_sector_ranking
  - reports_notification_queue
```

📸 **Print pedido na Entrega 4:** tire um print dessa saída no terminal, e também abra o MongoDB Compass (ou `mongosh`) para mostrar as coleções `reports_sector_ranking` e `reports_notification_queue` criadas pelo `$merge`. Salve ambos em `examples/`.
