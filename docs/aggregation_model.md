# Modelo de Agregação — EcoMonitor

> **O que é "agregação" no MongoDB?** É o processo de pegar vários documentos espalhados em uma ou mais coleções e "resumi-los" em uma resposta útil — por exemplo, somar, contar, ordenar, ou juntar informações de coleções diferentes. Isso é feito através de uma **pipeline de agregação**: uma sequência de "etapas" (`$match`, `$group`, `$sort`, `$lookup` etc.) que os dados atravessam, uma por uma, até chegar no resultado final. É equivalente ao `GROUP BY` e `JOIN` do SQL, só que mais flexível.

---

## Hierarquia de Informações (revisão)

```text
Building
 └── Sector
      └── Session
           ├── Readings (leituras brutas, densas)
           └── Event (leitura anômala: pico, consumo alto, sensor offline)
                └── Notification Status
```

Coleções de apoio:
- `buildings`: prédio monitorado.
- `sectors`: setor com sensor e threshold associados.
- `sessions`: janela diária de monitoramento por setor.
- `readings`: leituras periódicas brutas (dados densos, muitos documentos).
- `events`: documentos esparsos — só as leituras que dispararam algum alerta.
- `system_logs`: trilha operacional do sistema.

Essa hierarquia existe porque **cada nível responde a uma pergunta diferente**:
- `buildings` → "quais prédios eu monitoro?"
- `sectors` → "quais setores existem dentro de um prédio, e qual o limite normal de cada um?"
- `sessions` → "como foi o consumo de um setor num dia específico?"
- `events` → "o que deu errado, e quando?"

---

## Agregações que fazem sentido para a funcionalidade principal

Lembrando a funcionalidade central do sistema: **alertar o gestor sobre consumo anômalo a tempo de agir**. As agregações abaixo existem para sustentar essa funcionalidade — tanto para gerar os alertas quanto para dar visibilidade ao gestor sobre onde focar esforço.

### 1. Consumo médio por setor, em um período
**Pergunta que responde:** "Qual o consumo médio diário de cada setor no último mês?"
**Etapas envolvidas:** `$match` (filtra o período), `$group` (agrupa por `sector_id`, calcula média com `$avg`), `$sort` (ordena do maior para o menor consumo).
**Por que importa:** ajuda o gestor a identificar setores com padrão de consumo elevado mesmo sem ter disparado um evento ainda — prevenção antes do problema.

### 2. Ranking de setores por número de eventos de anomalia
**Pergunta que responde:** "Quais setores mais geram alertas?"
**Etapas envolvidas:** `$match` (filtra por tipo de evento), `$group` (conta eventos por `sector_id` com `$sum`), `$sort` + `$limit` (top 5), `$lookup` (busca o nome do setor na coleção `sectors`, já que `events` só guarda o `sector_id`).
**Por que importa:** aponta onde investir em manutenção elétrica — um setor que gera muitos alertas pode ter um problema estrutural, não só picos pontuais.

### 3. Relatório consolidado de eventos com dados do prédio e do setor
**Pergunta que responde:** "Me dê a lista de todos os alertas pendentes, já com o nome do prédio e do setor, não só os IDs."
**Etapas envolvidas:** `$match` (`notification.status: PENDING`), `$lookup` (duas vezes: uma para trazer dados de `sectors`, outra para trazer dados de `buildings`), `$unwind` (para "desempacotar" o resultado do `$lookup`, que vem como lista), `$project` (seleciona só os campos relevantes para exibir na tela do gestor).
**Por que importa:** é exatamente essa consulta que vai alimentar a tela principal da interface Streamlit (Entrega 3) — a lista de alertas que o gestor precisa resolver.

### 4. Total consumido por prédio, no mês, comparando setores
**Pergunta que responde:** "Quanto cada prédio gastou de energia esse mês, e como isso se distribui entre os setores?"
**Etapas envolvidas:** `$lookup` (junta `sessions` com `sectors` e `buildings`), `$group` (soma `total_consumption_kwh` por prédio), `$sort`.
**Por que importa:** dá visão executiva para quem administra múltiplos prédios (ex: uma administradora de condomínios).

---

## Observação sobre a Entrega 4

A ementa pede **2 pipelines de agregação completos** (não as 4 ideias soltas acima) usando os operadores `$sort`, `$match`, `$group`, `$lookup`, `$project`, `$unwind`, `$merge`, `$set`, `$sample`. Na Entrega 4, vamos escolher e implementar por completo duas destas quatro ideias (provavelmente a #2 e a #3, por serem as que mais sustentam a funcionalidade principal), além de criar **2 índices** no MongoDB para otimizar essas consultas (por exemplo, um índice em `events.sector_id` e outro em `events.notification.status`, já que são os campos mais filtrados).

> **O que é um "índice" no banco de dados?** É uma estrutura auxiliar que acelera buscas em campos específicos, evitando que o MongoDB precise varrer documento por documento toda vez. É parecido com o índice de um livro: em vez de ler o livro inteiro pra achar um assunto, você vai direto na página indicada.
