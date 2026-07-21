# EcoMonitor — Redis e Neo4j

Esta implementação segue a mesma estrutura do CineHub: dois scripts separados na raiz do projeto, um para Redis e outro para Neo4j/GDS.

## 1. Funcionalidades implementadas no Redis

### Funcionalidade 1 — Login e sessão do gestor

- `HASH`: armazena nome, e-mail e hash da senha do gestor.
- `STRING` com `TTL`: armazena o token temporário de sessão.
- `SET`: guarda os tokens das sessões ativas.

Fluxo demonstrado: cadastro do gestor, login correto, login incorreto, validação da sessão e logout.

### Funcionalidade 2 — Processamento de alertas

- `STRING` com `TTL`: cache dos alertas pendentes consultados no MongoDB.
- `Bloom Filter`: evita que o mesmo evento seja enviado duas vezes para a fila.
- `HyperLogLog`: estima quantos setores únicos geraram anomalias.
- `STREAM`: funciona como fila de mensagens para notificações.
- `ZSET`: gera ranking dos setores pela quantidade de eventos.

A primeira leitura dos alertas gera `cache MISS`; a segunda reutiliza a informação em memória e gera `cache HIT`. Isso reduz consultas repetidas ao MongoDB e reduz o impedance mismatch, pois o resultado já fica pronto em JSON no Redis.

> O Bloom Filter usa os comandos `BF.ADD` e `BF.EXISTS`, disponíveis no Redis Stack ou em instâncias Redis Cloud com RedisBloom. Em Redis comum, o código usa um `SET` como fallback para continuar funcionando.

## 2. Grafo implementado no Neo4j

### Nós

- `Building`: prédio monitorado.
- `Sector`: setor do prédio.
- `Sensor`: sensor associado ao setor.
- `Event`: evento de consumo anômalo.

### Relacionamentos

```text
(Building)-[:POSSUI]->(Sector)
(Sector)-[:MONITORADO_POR]->(Sensor)
(Sector)-[:GEROU]->(Event)
```

Os dados são lidos diretamente das coleções MongoDB já preenchidas pelo `simulator.py`.

## 3. Operação GDS escolhida

Foi utilizada **Degree Centrality** nos nós `Sector`.

Cada relacionamento `GEROU` liga um setor a um evento anômalo. Portanto, o grau de um setor corresponde à quantidade de eventos que ele gerou. O setor com maior `degree_score` é o setor que mais apresentou anomalias e deve receber maior prioridade de manutenção.

Caso o servidor Neo4j não tenha GDS, o script executa uma consulta Cypher equivalente e continua funcionando.

---

# Passo a passo de implementação

## Etapa 1 — Abrir o projeto e criar o ambiente

No terminal, dentro da pasta do projeto:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Etapa 2 — Criar o arquivo `.env`

Copie `.env.example` e renomeie para `.env`.

Preencha as credenciais reais do MongoDB, Redis e Neo4j:

```env
MONGO_URI=mongodb://ecomonitor:ecomonitor123@localhost:27017
MONGO_DB_NAME=ecomonitor

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_SSL=false
RESET_REDIS_DEMO=true

NEO4J_URI=neo4j+s://SEU-ID.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=SUA_SENHA
NEO4J_DATABASE=neo4j
```

Para Redis Cloud, use o host, porta, usuário, senha e SSL fornecidos no painel.

## Etapa 3 — Testar os bancos

MongoDB:

```bat
python src\storage\mongodb_client.py
```

Redis:

```bat
python src\storage\redis_client.py
```

## Etapa 4 — Gerar os dados do EcoMonitor

```bat
python src\storage\simulator.py
```

Esse comando deve criar prédios, setores, sensores por referência, sessões, leituras e eventos de anomalia no MongoDB.

## Etapa 5 — Executar o Redis

```bat
python redis_funcionalidades.py
```

A saída esperada deve mostrar:

1. conexão com Redis;
2. login correto e senha incorreta;
3. sessão com TTL;
4. cache `MISS` e depois `HIT`;
5. alertas enviados para o Stream;
6. eventos duplicados bloqueados;
7. HyperLogLog com setores únicos;
8. ranking ZSET;
9. lista final de chaves Redis.

## Etapa 6 — Criar uma instância Neo4j

No Neo4j Aura:

1. crie uma instância;
2. copie a URI, usuário e senha;
3. coloque as informações no `.env`;
4. aguarde a instância ficar disponível.

Também é possível usar Neo4j local, alterando:

```env
NEO4J_URI=neo4j://localhost:7687
```

## Etapa 7 — Executar o grafo e o GDS

```bat
python neo4j_ecomonitor.py
```

A saída deve mostrar:

1. quantidade de documentos lidos no MongoDB;
2. criação dos nós e relacionamentos;
3. consultas Cypher;
4. ranking de setores pela Degree Centrality;
5. resumo do grafo.

## Etapa 8 — Visualizar o grafo no Neo4j Browser

Execute:

```cypher
MATCH (b:Building)-[:POSSUI]->(s:Sector)-[:GEROU]->(e:Event)
RETURN b, s, e
LIMIT 50;
```

Para incluir os sensores:

```cypher
MATCH (b:Building)-[:POSSUI]->(s:Sector)-[:MONITORADO_POR]->(sensor:Sensor)
RETURN b, s, sensor;
```

Para consultar o resultado de criticidade salvo nos setores:

```cypher
MATCH (s:Sector)
RETURN s.name AS setor, s.degree_score AS criticidade
ORDER BY criticidade DESC;
```

# Prints recomendados para a entrega

1. Terminal do Redis mostrando login e sessão.
2. Terminal mostrando `cache MISS` e `cache HIT`.
3. Terminal mostrando Bloom Filter/fallback, Stream e eventos duplicados.
4. Terminal mostrando HyperLogLog e ranking ZSET.
5. Neo4j Browser com o grafo completo.
6. Terminal mostrando o ranking GDS Degree Centrality.
7. Consulta Cypher com `degree_score` dos setores.
