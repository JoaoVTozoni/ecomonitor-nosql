# Coleções do banco `ecomonitor`

> **O que é uma "coleção"?** No MongoDB, uma coleção é equivalente a uma "tabela" do SQL, mas sem estrutura fixa: cada documento (linha) dentro dela pode ter campos diferentes. Aqui vamos manter cada coleção com uma estrutura consistente por clareza, mas isso é uma escolha nossa, não uma obrigação do banco.

Este projeto usa **5 coleções**, seguindo a hierarquia `Building → Sector → Session → Event`, mais uma coleção auxiliar de auditoria (`system_logs`).

---

## 1. Coleção: `buildings`

Representa cada prédio monitorado. É o nível mais alto da hierarquia.

**Armazena:**
- nome/identificação do prédio
- endereço
- quantidade de setores cadastrados
- status geral (ativo/inativo)

**Exemplo de documento:**
```json
{
  "_id": "bld_001",
  "name": "Edifício Aurora",
  "address": "Rua das Palmeiras, 123 - Araxá/MG",
  "total_sectors": 4,
  "status": "active",
  "created_at": "2026-06-01T08:00:00Z"
}
```

---

## 2. Coleção: `sectors`

Representa um setor/andar de um prédio, cada um associado a um sensor de energia (simulado).

**Armazena:**
- identificador do sensor
- prédio ao qual pertence (referência ao `_id` de `buildings`)
- limite de consumo considerado normal (threshold), usado para decidir quando gerar um evento
- status operacional do sensor

**Exemplo de documento:**
```json
{
  "_id": "sec_001",
  "building_id": "bld_001",
  "name": "3º Andar - Ala Norte",
  "sensor_id": "sensor_a17",
  "threshold_kwh": 12.5,
  "status": "online",
  "last_seen": "2026-07-06T14:32:00Z"
}
```
> **Por que guardamos `threshold_kwh` aqui e não em outro lugar?** Porque o limite de consumo "normal" é uma característica do setor (um data center consome mais que um corredor, por exemplo). É esse valor que o sistema vai comparar com as leituras para decidir se cria um evento.

---

## 3. Coleção: `sessions`

Representa uma janela de monitoramento (por padrão, um dia) de um setor específico.

**Armazena:**
- setor associado (referência a `sectors`)
- horário de início/fim da janela
- consumo total acumulado na sessão
- status (aberta/fechada)

**Exemplo de documento:**
```json
{
  "_id": "ses_20260706_sec001",
  "sector_id": "sec_001",
  "date": "2026-07-06",
  "started_at": "2026-07-06T00:00:00Z",
  "closed_at": null,
  "total_consumption_kwh": 187.4,
  "status": "open"
}
```
> Uma sessão é "fechada" ao fim do dia, quando somamos todas as leituras daquele setor naquele dia. É esse documento que facilita perguntas do tipo "quanto o 3º andar gastou ontem", sem precisar somar centenas de leituras brutas toda vez.

---

## 4. Coleção: `readings` (coleção densa — leituras brutas)

Armazena as leituras periódicas de energia (ex: a cada 15 minutos), geradas pelo simulador. É a coleção com mais documentos, mas cada documento é pequeno e simples.

**Armazena:**
- setor e sessão associados
- timestamp da leitura
- valor de consumo (kWh) naquele intervalo

**Exemplo de documento:**
```json
{
  "_id": "read_00098231",
  "sector_id": "sec_001",
  "session_id": "ses_20260706_sec001",
  "timestamp": "2026-07-06T14:30:00Z",
  "consumption_kwh": 0.42
}
```

---

## 5. Coleção: `events` (coleção esparsa — o coração do sistema)

Armazena **apenas** as leituras consideradas anômalas: pico de consumo, consumo acima do threshold do setor, ou sensor que parou de enviar dados. É esta coleção que alimenta a funcionalidade principal do sistema (o alerta ao gestor).

**Armazena:**
- setor, sessão e prédio relacionados
- tipo do evento (`HIGH_CONSUMPTION`, `SPIKE`, `SENSOR_OFFLINE`)
- valor que disparou o evento
- status da notificação ao gestor (`PENDING` / `SENT`)

**Exemplo de documento:**
```json
{
  "_id": "evt_00master15",
  "sector_id": "sec_001",
  "session_id": "ses_20260706_sec001",
  "building_id": "bld_001",
  "event_type": "HIGH_CONSUMPTION",
  "value_kwh": 15.8,
  "threshold_kwh": 12.5,
  "detected_at": "2026-07-06T14:30:00Z",
  "notification": {
    "enabled": true,
    "status": "PENDING",
    "sent_at": null
  },
  "demo": false
}
```
> Note o campo `demo: false`. Vamos usar esse campo para marcar documentos criados só para fins de demonstração do CRUD (Entrega 3), assim conseguimos apagá-los depois sem mexer em dados "reais" da simulação — igual ao projeto de referência que inspirou este trabalho.

---

## 6. Coleção: `system_logs` (auditoria)

Registra eventos operacionais do próprio sistema (não do consumo elétrico): abertura/fechamento de sessão, alerta disparado, sensor caiu etc. Serve para auditoria e para provar, no CRUD, que o sistema está "vivo".

**Exemplo de documento:**
```json
{
  "_id": "log_000441",
  "type": "SESSION_OPENED",
  "sector_id": "sec_001",
  "message": "Sessão de monitoramento iniciada para o setor 3º Andar - Ala Norte",
  "timestamp": "2026-07-06T00:00:00Z"
}
```
