# EcoMonitor — Monitoramento NoSQL de Consumo de Energia Elétrica

Sistema NoSQL para armazenamento esparso de eventos de consumo elétrico anômalo em prédios/setores, com foco em prevenção de desperdício e alertas em tempo hábil.

## 👥 Integrantes
- João Victor Tozoni
- Maria Clara de Freitas

---

## 🗺️ Roteiro do Projeto (Roadmap rápido)
> **Consulte o arquivo [`ROADMAP.md`](ROADMAP.md) para ver o mapeamento passo a passo de todas as entregas do projeto, caminhos de códigos, explicações das pipelines e chaves do Redis.**
> 
> *Nota: O projeto foi aprimorado com um ambiente Docker unificado (`docker-compose.yaml` no diretório raiz) e a interface Streamlit agora conta com abas interativas integradas para **Redis** e **Neo4j + GDS**.*

---

## 📌 Tema do Projeto

Prédios (residenciais, escolas, empresas) costumam descobrir que gastaram energia demais só quando a conta chega no fim do mês — tarde demais para agir.

Este projeto propõe uma arquitetura NoSQL que **monitora o consumo elétrico de vários setores de um prédio em tempo quase real**, registrando leituras periódicas dos "sensores" (simulados, sem hardware real) e — o mais importante — **detectando e armazenando apenas os eventos relevantes**: picos de consumo, consumo fora do padrão esperado, ou sensores que pararam de responder.

> **Por que "armazenamento esparso"?** Guardar *toda* leitura de energia de todo sensor a cada minuto, para sempre, geraria um volume gigante de dados repetitivos e pouco úteis. Em vez disso, o sistema guarda as leituras brutas por um tempo (coleção densa), mas cria **documentos de evento** só quando algo *importa* de fato (coleção esparsa). É a mesma lógica usada em sistemas de câmeras de segurança: não se grava "nada aconteceu" — grava-se o evento.

### Funcionalidade que mais entrega valor
**Alertar automaticamente o responsável pelo prédio (síndico/gestor) quando um setor está consumindo energia acima do esperado, antes que isso vire um problema financeiro ou de segurança (sobrecarga elétrica).**

Guardar dados sozinho não resolve o problema do usuário — o valor real está em **avisar a tempo**. Essa funcionalidade é o fio condutor de todas as entregas: a estrutura de coleções existe pra sustentar esse alerta, a interface existe pra mostrar esse alerta, e as agregações existem pra dar visibilidade sobre onde os alertas mais acontecem.

---

## 🧩 Hierarquia de Informações

```text
Building (prédio)
 └── Sector (setor/andar, com sensor associado)
      └── Session (janela diária de monitoramento)
           ├── Readings (leituras brutas periódicas)
           └── Event (leitura anômala: pico, consumo fora do padrão, sensor offline)
```

> No MongoDB, cada nível dessa hierarquia vira uma **coleção** — uma "gaveta" de documentos — e os documentos se referenciam por um ID, parecido com uma chave estrangeira, mas sem a rigidez do SQL. Detalhes de cada coleção e exemplo de documento em [`docs/collections.md`](docs/collections.md).

---

## 📅 Entrega 1 — Tema e funcionalidade principal
Definição do tema (acima) e da funcionalidade que mais entrega valor: alertar o gestor a tempo, não apenas armazenar dados de consumo.

---

## 📅 Entrega 2 — Modelo de agregação e coleções
Documentado em [`docs/collections.md`](docs/collections.md) (as 6 coleções, cada uma com exemplo de documento JSON) e [`docs/aggregation_model.md`](docs/aggregation_model.md) (hierarquia completa e as 4 agregações pensadas para sustentar o alerta ao gestor).

---

## 📅 Entrega 3 — CRUD com protótipo em Streamlit

Construímos uma interface em Streamlit com 3 abas, todas conectadas ao MongoDB local. Abaixo, cada tela explicada em detalhe.

### Aba "Alertas (Events)" — a funcionalidade principal do sistema

![Alertas pendentes](examples/Captura%20de%20tela%202026-07-07%20160829.png)

Esta tela é o coração do EcoMonitor: mostra os eventos de consumo anômalo (`events`) já cruzados com o nome do setor e do prédio, usando uma pipeline de agregação com `$match` (filtra por status), `$lookup` (busca os nomes nas coleções `sectors` e `buildings`) e `$project` (seleciona os campos exibidos). O filtro **PENDING / SENT / Todos** no topo troca o `$match` da consulta em tempo real. Cada card mostra o consumo registrado (ex: `12.326 kWh`) comparado ao limite do setor (ex: `limite: 8.0 kWh`), e o botão **"Marcar como resolvido"** dispara a operação de **UPDATE**, mudando `notification.status` de `PENDING` para `SENT`.

![Alerta marcado como SENT](examples/Captura%20de%20tela%202026-07-07%20161121.png)

Aqui o filtro está em **SENT**, mostrando que o alerta do setor "Área Comum / Lazer" já foi marcado como resolvido — prova de que o UPDATE funcionou e persistiu no banco.

![Filtro Todos misturando status](examples/Captura%20de%20tela%202026-07-07%20161130.png)

Com o filtro em **Todos**, a tela mostra alertas com os dois status ao mesmo tempo (um `SENT` e outros `PENDING`), confirmando que a query e o botão de ação convivem corretamente.

### Aba "Setores (Sectors)" — gestão dos setores monitorados

![Lista de setores](examples/Captura%20de%20tela%202026-07-07%20160838.png)

Lista os 4 setores cadastrados (`sectors`), cada um com seu sensor associado e o limite de consumo (`threshold_kwh`) configurável. Alterar o número e clicar em **"Salvar"** executa um **UPDATE** direto no campo `threshold_kwh` daquele setor — é esse valor que a simulação usa para decidir quando um evento de anomalia deve ser criado.

![Lista de setores (revisão)](examples/Captura%20de%20tela%202026-07-07%20161154.png)

Mesma tela, confirmando que os 4 setores continuam consistentes após interações anteriores na aba de Alertas.

![Formulário de novo setor](examples/Captura%20de%20tela%202026-07-07%20161202.png)

Abaixo da lista, um formulário permite cadastrar um **novo** setor (ID, nome, sensor e limite de consumo). Ao confirmar, o sistema executa um **INSERT** na coleção `sectors` — essa é a mesma coleção que sustenta o resto do sistema, então um setor criado aqui já passa a ser monitorado pelo simulador na próxima execução.

### Aba "Demonstração CRUD" — as 4 operações isoladas, para prova de conceito

Como a Entrega 3 pede evidência explícita de INSERT, FIND, UPDATE e DELETE, criamos uma aba dedicada com um botão para cada operação, sempre atuando sobre documentos marcados com `demo: true` — isso evita misturar dados de teste com os dados "reais" gerados pelo simulador.

![Botões da demonstração CRUD](examples/Captura%20de%20tela%202026-07-07%20160859.png)

Os 4 botões disponíveis, cada um isolado, para poder tirar um print de cada operação separadamente.

![INSERT — documento criado](examples/Captura%20de%20tela%202026-07-07%20160922.png)

Ao clicar em **INSERT**, o sistema cria um documento de evento de demonstração (`evt_demo_...`) com `value_kwh: 99.9` e `demo: true`, e exibe o JSON completo do documento inserido — prova visual da operação `insert_one()`.

![FIND — documentos encontrados](examples/Captura%20de%20tela%202026-07-07%20161000.png)

Ao clicar em **FIND**, o sistema busca todos os documentos com `demo: true` (nesse print, encontrou 5, resultado de cliques repetidos em INSERT) e lista o JSON de cada um — prova da operação `find()`.

![UPDATE — documentos atualizados](examples/Captura%20de%20tela%202026-07-07%20161039.png)

Ao clicar em **UPDATE**, o sistema executa `update_many()` sobre todos os documentos de demonstração, mudando `notification.status` para `SENT` — a mensagem "5 documento(s) atualizado(s)" confirma quantos registros foram afetados.

![DELETE — documentos apagados](examples/Captura%20de%20tela%202026-07-07%20161059.png)

Por fim, o botão **DELETE** executa `delete_many({"demo": True})`, removendo só os documentos de teste e preservando os dados reais da simulação — a mensagem "5 documento(s) apagado(s)" confirma a limpeza.

---

## 📅 Entrega 4 — Pipelines de agregação e índices

### Índices
Criados em `src/storage/mongodb_client.py` (`ensure_indexes()`): `events.sector_id` e `events.notification.status`. Aceleram exatamente as consultas usadas nos pipelines abaixo e na aba de Alertas, evitando que o MongoDB precise varrer a coleção `events` inteira a cada busca.

### Execução dos 2 pipelines (`src/storage/aggregations.py`)

![Log de execução dos 2 pipelines](examples/Captura%20de%20tela%202026-07-07%20171428.png)

Saída do terminal rodando `python3 src/storage/aggregations.py`. O bloco **Pipeline 1** mostra o ranking dos 4 setores por número de eventos de anomalia, com consumo médio, pico e severidade calculada (`$match` → `$group` → `$sort` → `$lookup` → `$unwind` → `$set` → `$project` → `$merge`). O bloco **Pipeline 2** mostra uma amostra aleatória de 5 alertas pendentes, já com a mensagem de notificação formatada e pronta (`$match` → `$sample` → `$lookup` → `$unwind` → `$set` → `$project` → `$sort` → `$merge`).

![mongosh mostrando as coleções de relatório](examples/Captura%20de%20tela%202026-07-07%20171555.png)

Consulta direta via `mongosh` confirmando que o `$merge` de cada pipeline realmente gravou os resultados em coleções próprias: `reports_sector_ranking` (saída do Pipeline 1) e `reports_notification_queue` (saída do Pipeline 2) — prova de que a agregação não fica só no console, ela persiste no banco para consumo por outras telas.

![Segunda consulta via mongosh](examples/Captura%20de%20tela%202026-07-07%20171627.png)

Nova consulta confirmando a consistência dos dados gravados após a correção de um bug inicial (a primeira versão da pipeline duplicava registros a cada execução por não manter o `_id` do setor no `$project`; corrigido para reter `_id: "$_id"`, permitindo que o `$merge` atualize em vez de duplicar).

![Aba Relatórios no Streamlit](examples/Captura%20de%20tela%202026-07-07%20174717.png)

Como complemento (não exigido pela ementa, mas somado para deixar o sistema coeso), adicionamos uma 4ª aba **"📊 Relatórios"** no Streamlit, que lê diretamente das coleções `reports_sector_ranking` e `reports_notification_queue` — mostrando visualmente o ranking de setores mais problemáticos e a fila de alertas prontos para notificação, sem precisar rodar o script manualmente para ver o resultado.

Detalhamento completo de cada etapa das 2 pipelines em [`docs/entrega4.md`](docs/entrega4.md).

---

## ⚙️ Como executar o projeto

Guia completo, comando por comando (Docker, Python, Streamlit), em [`docs/como_executar.md`](docs/como_executar.md).

---

## 📁 Estrutura do repositório

```text
ecomonitor-nosql/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── collections.md          (Entrega 2)
│   ├── aggregation_model.md    (Entrega 2)
│   ├── como_executar.md        (Entrega 3)
│   └── entrega4.md             (Entrega 4)
├── infrastructure/
│   └── mongodb/docker-compose.yaml   (Entrega 3)
├── src/
│   ├── storage/
│   │   ├── mongodb_client.py   (Entrega 3)
│   │   ├── simulator.py        (Entrega 3)
│   │   └── aggregations.py     (Entrega 4)
│   └── app/
│       └── streamlit_app.py    (Entrega 3 + Entrega 4)
└── examples/                    (prints de todas as entregas)
```

---

## 📅 Entrega 5 — Redis e Grafos com Neo4j

Foram adicionados dois scripts independentes, seguindo a mesma estrutura usada pelo projeto CineHub:

- `redis_funcionalidades.py`: login e sessão do gestor; cache de alertas; Bloom Filter; HyperLogLog; Redis Stream; ranking com ZSET.
- `neo4j_ecomonitor.py`: cria o grafo `Building → Sector → Event`, relaciona sensores e executa **GDS Degree Centrality** para identificar os setores com mais anomalias.

O passo a passo completo está em [`docs/entrega_redis_neo4j.md`](docs/entrega_redis_neo4j.md).
