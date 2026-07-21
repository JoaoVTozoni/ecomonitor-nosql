# 🗺️ Guia de Entregas e Etapas do Projeto — EcoMonitor

Este documento mapeia todas as etapas solicitadas pela disciplina, indicando exatamente onde cada funcionalidade, script, banco de dados e evidência de teste (prints e logs) está localizada no repositório.

---

## 📌 Mapa Geral do Projeto

| Etapa / Requisito | Descrição | Localização no Repositório |
| :--- | :--- | :--- |
| **1. Tema do Projeto** | Definição do tema e contexto de monitoramento de energia | [README.md (Tema)](README.md#tema-do-projeto) |
| **2. Funcionalidade de Maior Valor** | Alerta tempestivo de consumo anômalo ao gestor | [README.md (Valor)](README.md#funcionalidade-que-mais-entrega-valor) |
| **3. Hierarquia de Informações** | Estruturação de dados: Prédio ➡️ Setor ➡️ Sessão ➡️ Leitura/Evento | [README.md (Hierarquia)](README.md#hierarquia-de-informações) |
| **4. Definição das Coleções (Exemplos)** | Detalhamento e exemplos JSON de cada coleção MongoDB | [docs/collections.md](docs/collections.md) |
| **5. Modelo de Agregação Teórico** | Relação de pipelines pensadas para a funcionalidade principal | [docs/aggregation_model.md](docs/aggregation_model.md) |
| **6. Protótipo da Interface Streamlit** | Dashboard visual do sistema integrado | [src/app/streamlit_app.py](src/app/streamlit_app.py) |
| **7. Criação e População das Coleções** | Simulador de dados em tempo real para o MongoDB | [src/storage/simulator.py](src/storage/simulator.py) |
| **8. CRUD completo e visível** | Tela Streamlit com botões explícitos para INSERT, FIND, UPDATE, DELETE | [src/app/streamlit_app.py (Aba Demonstração)](src/app/streamlit_app.py#L225) |
| **9. 2 Pipelines de Agregação com $merge** | Ranking de Setores (Pipeline 1) e Amostra de Notificações (Pipeline 2) | [src/storage/aggregations.py](src/storage/aggregations.py) |
| **10. Índices no MongoDB** | Otimização em `events.sector_id` e `events.notification.status` | [src/storage/mongodb_client.py](src/storage/mongodb_client.py#L35) |
| **11. Recursos com Redis** | Login HASH/SET, cache TTL, HLL de setores, ZSET ranking e Streams | [redis_funcionalidades.py](redis_funcionalidades.py) |
| **12. Grafo e GDS no Neo4j** | Grafo do monitoramento e Degree Centrality para criticidade | [neo4j_ecomonitor.py](neo4j_ecomonitor.py) |
| **13. Prints e Evidências Visuais** | Imagens das telas, dados nos bancos e execuções de terminal | [examples/](examples/) |

---

## ⚡ Detalhamento das Etapas e Funcionalidades

### 1️⃣ Tema e Funcionalidade de Valor
- **Tema:** Monitoramento NoSQL de consumo esparso e anômalo de eletricidade em prédios.
- **Funcionalidade Principal:** Alertar o gestor (síndico/administrador) sobre anomalias em setores antes que a fatura mensal feche.
- **Localização:** Detalhado nas seções correspondentes do [README.md](README.md).

### 2️⃣ Hierarquia de Informações e Coleções
- **Hierarquia:** `Building` ➡️ `Sector` (monitorado por `Sensor`) ➡️ `Session` (uma janela de dia) ➡️ `Readings` (leituras a cada 15 min) e `Events` (documentos gerados somente no consumo excessivo).
- **Especificação:** Cada coleção tem sua descrição de atributos e um exemplo em formato JSON no arquivo [docs/collections.md](docs/collections.md). O modelo conceitual de agregações está em [docs/aggregation_model.md](docs/aggregation_model.md).

### 3️⃣ Protótipo Streamlit & Operações CRUD
- **Interface:** O arquivo [src/app/streamlit_app.py](src/app/streamlit_app.py) contém a aplicação completa.
- **CRUD Principal:**
  - **INSERT:** Adiciona novo setor na aba "Setores" ou cria evento de teste na aba "Demonstração CRUD".
  - **FIND:** Lista eventos pendentes na aba "Alertas" e busca itens de teste na aba "Demonstração CRUD".
  - **UPDATE:** Altera limite do setor (Aba Setores), marca alerta como resolvido (Aba Alertas) ou atualiza múltiplos na demonstração.
  - **DELETE:** Limpa dados de demonstração (Aba Demonstração CRUD).
- **Evidências:** Imagens cobrindo cada clique de operação salvos na pasta [examples/](examples/).

### 4️⃣ Pipelines de Agregação (MongoDB)
- **Script de Execução:** [src/storage/aggregations.py](src/storage/aggregations.py).
- **Pipeline 1 (Ranking de Setores):** Agrupa os eventos por setor (`$group` + `$sum` + `$avg`), traz dados do setor e prédio (`$lookup` + `$unwind`), calcula criticidade (`$set` com `$cond`), projeta os dados (`$project`) e persiste o resultado (`$merge` em `reports_sector_ranking`).
- **Pipeline 2 (Amostra de Alertas):** Sorteia alertas pendentes (`$match` + `$sample`), formata string de notificação (`$set` com `$concat` + `$toString`), ordena por criticidade (`$sort`) e grava (`$merge` em `reports_notification_queue`).
- **Visualização:** Exibido em tempo real na aba "Relatórios" do Streamlit.

### 5️⃣ Recursos com Redis
- **Script de Demonstração:** [redis_funcionalidades.py](redis_funcionalidades.py).
- **Estruturas Utilizadas:**
  - `HASH`: Armazena dados cadastrais do Gestor (ID, e-mail, hash de senha).
  - `STRING` com `TTL`: Cache temporário dos alertas pendentes (evita consultas ao MongoDB) e token de sessão ativa.
  - `SET`: Armazena tokens das sessões ativas.
  - `ZSET` (Sorted Set): Ranking de criticidade em tempo real dos setores por número de eventos de anomalia.
  - `STREAM`: Fila persistente de mensagens de alertas prontas para envio.
  - `HyperLogLog`: Estimativa probabilística de setores únicos com anomalias (`ecomonitor:hll:setores_com_anomalia`).
  - `Bloom Filter`: Filtro probabilístico (`BF.EXISTS` / `BF.ADD`) para deduplicar eventos (impede enviar o mesmo alerta duas vezes na fila). Se o módulo RedisBloom não estiver presente, usa um `SET` como fallback.
- **Visualização:** Integrado diretamente na aba "Redis" da interface Streamlit.

### 6️⃣ Grafo e Algoritmo GDS (Neo4j)
- **Script de Importação e Análise:** [neo4j_ecomonitor.py](neo4j_ecomonitor.py).
- **Modelagem do Grafo:**
  - Nós: `(:Building)`, `(:Sector)`, `(:Sensor)`, `(:Event)`.
  - Relacionamentos: `(:Building)-[:POSSUI]->(:Sector)`, `(:Sector)-[:MONITORADO_POR]->(:Sensor)`, `(:Sector)-[:GEROU]->(:Event)`.
- **Algoritmo GDS (Degree Centrality):** Mede a quantidade de conexões entre setores e eventos anômalos. Setores com maior grau representam locais críticos de desperdício ou falhas na instalação.
- **Fallback:** Executado via biblioteca Neo4j GDS integrada ou através de query Cypher nativa caso o plugin GDS não esteja ativado no servidor Neo4j.
- **Visualização:** Integrado diretamente na aba "Neo4j" da interface Streamlit.

---

## 🛠️ Como Executar Todo o Projeto Localmente

Suba os três bancos de dados de forma unificada usando o Docker:

```bash
# 1. Inicie todos os containers (MongoDB, Redis Stack, Neo4j + GDS)
docker compose up -d

# 2. Ative o ambiente Python e instale dependências
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Crie o arquivo .env a partir do template e configure as portas locais
cp .env.example .env

# 4. Inicialize os índices e popule o MongoDB
python src/storage/mongodb_client.py
python src/storage/simulator.py

# 5. Rode a interface unificada Streamlit
streamlit run src/app/streamlit_app.py
```
