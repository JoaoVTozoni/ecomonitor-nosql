# Como rodar a Entrega 3 (WSL + Docker)

## 1. Subir o MongoDB
No terminal do WSL, na raiz do projeto:
```bash
docker compose -f infrastructure/mongodb/docker-compose.yaml up -d
```
Isso baixa a imagem do MongoDB (na primeira vez) e sobe o container em segundo plano.
Confirme que está rodando:
```bash
docker ps
```
Você deve ver um container chamado `ecomonitor_mongo`.

## 2. Preparar o ambiente Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configurar variáveis de ambiente
```bash
cp .env.example .env
```
(não precisa editar nada, os valores padrão já batem com o docker-compose)

## 4. Criar os índices (uma vez só)
```bash
python3 src/storage/mongodb_client.py
```
Isso conecta no banco e cria os 2 índices usados pelas consultas (Entrega 4).

## 5. Popular o banco com dados simulados
```bash
python3 src/storage/simulator.py
```
Esse comando cria o prédio, os 4 setores, e simula 3 dias de leituras de energia
para cada setor — gerando eventos de anomalia automaticamente quando o consumo
ultrapassa o limite (threshold) de cada setor.

Você deve ver uma saída parecida com:
```
Base zerada. Gerando novos dados...
Criado 1 prédio e 4 setores.

Simulando os últimos 3 dias de consumo...

Dia -2:
  - 3º Andar - Ala Norte: 96 leituras, 6 evento(s) de anomalia.
  ...
Simulação concluída. Banco populado com sucesso.
```
**Tire um print dessa saída no terminal** — é uma das evidências pedidas na Entrega 3.

## 6. Rodar a interface Streamlit
```bash
streamlit run src/app/streamlit_app.py
```
Isso abre automaticamente uma aba no navegador (geralmente `http://localhost:8501`).

Na tela, você vai encontrar 3 abas:
- **🚨 Alertas (Events)**: mostra os eventos pendentes com nome do setor/prédio (usa `$lookup`), e permite marcar como resolvido (UPDATE)
- **🏢 Setores (Sectors)**: lista, edita (UPDATE) e permite criar (INSERT) novos setores
- **🧪 Demonstração CRUD**: 4 botões isolados para INSERT, FIND, UPDATE e DELETE — pensados exatamente para você tirar um print de cada operação separadamente

## 7. Tirar os prints pedidos na Entrega 3
Sugestão de prints a colocar na pasta `examples/`:
1. Terminal com a saída do `simulator.py`
2. Tela do Streamlit, aba "Alertas", mostrando eventos pendentes
3. Tela do Streamlit, aba "Demonstração CRUD", após clicar em INSERT (mostrando o JSON criado)
4. Mesma aba, após clicar em FIND (mostrando o documento encontrado)
5. Mesma aba, após clicar em UPDATE (mostrando "1 documento atualizado")
6. Mesma aba, após clicar em DELETE (mostrando "1 documento apagado")
7. MongoDB Compass (opcional, mas recomendado) conectando em `mongodb://ecomonitor:ecomonitor123@localhost:27017`, mostrando as coleções populadas

## Se algo der errado
- **Erro de conexão recusada**: o container do Mongo não subiu. Rode `docker ps` para confirmar, e `docker compose -f infrastructure/mongodb/docker-compose.yaml logs` para ver o erro.
- **`ModuleNotFoundError`**: esqueceu de ativar o ambiente virtual (`source venv/bin/activate`) ou de instalar as dependências.
- **Streamlit não abre no navegador automaticamente (comum no WSL)**: copie a URL que aparece no terminal (algo como `http://localhost:8501`) e cole manualmente no navegador do Windows.
