"""
streamlit_app.py — EcoMonitor UI

A interface visual unificada do EcoMonitor, integrando MongoDB (CRUD & Relatórios),
Redis (Sessões, Cache, Streams & HLL/ZSET) e Neo4j (Grafos & Degree Centrality).
"""

import sys
import os
from datetime import datetime
import streamlit as st

# Garante a importação dos módulos da pasta src/storage e raiz
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "storage"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from mongodb_client import get_database, check_mongodb_connection  # noqa: E402
from redis_client import get_redis, check_redis_connection  # noqa: E402

st.set_page_config(
    page_title="EcoMonitor — Painel NoSQL",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS customizada para visual premium
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .db-status-ok {
        background-color: rgba(40, 167, 69, 0.15);
        border: 1px solid rgba(40, 167, 69, 0.3);
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .db-status-err {
        background-color: rgba(220, 53, 69, 0.15);
        border: 1px solid rgba(220, 53, 69, 0.3);
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Verificação de Conexão com os Bancos
# ---------------------------------------------------------------------------
mongo_ok = check_mongodb_connection()
redis_ok = check_redis_connection()

# Verificador de Neo4j seguro
neo4j_ok = False
try:
    from neo4j_ecomonitor import EcoMonitorGraph
    # Testa conexão
    graph = EcoMonitorGraph()
    graph.testar_conexao()
    graph.close()
    neo4j_ok = True
except Exception:
    pass

# Sidebar com o status de cada banco
with st.sidebar:
    st.image("https://img.icons8.com/color/96/electricity.png", width=80)
    st.title("EcoMonitor")
    st.markdown("Monitoramento Inteligente de Consumo Energético com Bancos NoSQL.")
    st.divider()
    st.subheader("🔌 Status das Conexões")
    
    if mongo_ok:
        st.markdown('<div class="db-status-ok">🟢 MongoDB: <b>Online</b></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="db-status-err">🔴 MongoDB: <b>Offline</b></div>', unsafe_allow_html=True)
        
    if redis_ok:
        st.markdown('<div class="db-status-ok">🟢 Redis: <b>Online</b></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="db-status-err">🔴 Redis: <b>Offline</b></div>', unsafe_allow_html=True)
        
    if neo4j_ok:
        st.markdown('<div class="db-status-ok">🟢 Neo4j + GDS: <b>Online</b></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="db-status-err">🔴 Neo4j + GDS: <b>Offline</b></div>', unsafe_allow_html=True)

    st.divider()
    st.caption("Desenvolvido por João Victor Tozoni & Maria Clara de Freitas")

st.title("⚡ EcoMonitor — Painel de Controle Multibancos NoSQL")

# Abas principais
tab_events, tab_sectors, tab_crud_demo, tab_reports, tab_redis, tab_neo4j = st.tabs(
    [
        "🚨 Alertas (MongoDB)", 
        "🏢 Setores (MongoDB)", 
        "🧪 Demonstração CRUD", 
        "📊 Relatórios (Entrega 4)",
        "🔑 Redis (Entrega 5)",
        "🕸️ Neo4j (Entrega 5)"
    ]
)

# ---------------------------------------------------------------------------
# ABA 1: Alertas pendentes (MongoDB)
# ---------------------------------------------------------------------------
with tab_events:
    st.subheader("Alertas de consumo anômalo no MongoDB")
    if not mongo_ok:
        st.error("⚠️ O MongoDB está desconectado. Suba a instância local com 'docker compose up -d' ou verifique o arquivo .env.")
    else:
        db = get_database()
        st.caption(
            "Esta consulta usa $match (filtra por status), $lookup (busca setores e prédios) e $project - "
            "corresponde à consulta de alertas pendentes estruturada no MongoDB."
        )

        status_filter = st.radio("Filtrar por status:", ["PENDING", "SENT", "Todos"], horizontal=True, key="evt_status_filter")

        match_stage = {}
        if status_filter != "Todos":
            match_stage = {"notification.status": status_filter}

        pipeline = [
            {"$match": match_stage},
            {
                "$lookup": {
                    "from": "sectors",
                    "localField": "sector_id",
                    "foreignField": "_id",
                    "as": "sector_info",
                }
            },
            {"$unwind": "$sector_info"},
            {
                "$lookup": {
                    "from": "buildings",
                    "localField": "building_id",
                    "foreignField": "_id",
                    "as": "building_info",
                }
            },
            {"$unwind": "$building_info"},
            {
                "$project": {
                    "event_type": 1,
                    "value_kwh": 1,
                    "threshold_kwh": 1,
                    "detected_at": 1,
                    "notification.status": 1,
                    "sector_name": "$sector_info.name",
                    "building_name": "$building_info.name",
                }
            },
            {"$sort": {"detected_at": -1}},
        ]

        events = list(db.events.aggregate(pipeline))

        if not events:
            st.info("Nenhum evento encontrado para esse filtro.")
        else:
            for ev in events:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.markdown(f"**{ev['building_name']} — {ev['sector_name']}**")
                        st.caption(f"Tipo: {ev['event_type']} | Detectado em: {ev['detected_at']}")
                    with col2:
                        st.metric("Consumo", f"{ev['value_kwh']} kWh", delta=f"limite: {ev['threshold_kwh']} kWh")
                    with col3:
                        current_status = ev["notification"]["status"]
                        st.write(f"Status: **{current_status}**")
                        if current_status == "PENDING":
                            if st.button("✅ Marcar como resolvido", key=f"resolve_{ev['_id']}"):
                                db.events.update_one(
                                    {"_id": ev["_id"]},
                                    {"$set": {
                                        "notification.status": "SENT",
                                        "notification.sent_at": datetime.utcnow(),
                                    }},
                                )
                                st.success("Alerta marcado como resolvido!")
                                st.rerun()

# ---------------------------------------------------------------------------
# ABA 2: Gestão de setores (MongoDB)
# ---------------------------------------------------------------------------
with tab_sectors:
    st.subheader("Setores Monitorados no MongoDB")
    if not mongo_ok:
        st.error("⚠️ O MongoDB está desconectado.")
    else:
        db = get_database()
        sectors = list(db.sectors.find())
        for sec in sectors:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{sec['name']}** ({sec['_id']})")
                    st.caption(f"Sensor: {sec['sensor_id']} | Status: {sec['status']}")
                with col2:
                    new_threshold = st.number_input(
                        "Limite (kWh)", value=float(sec["threshold_kwh"]),
                        key=f"threshold_{sec['_id']}"
                    )
                with col3:
                    if st.button("Salvar", key=f"save_{sec['_id']}"):
                        db.sectors.update_one(
                            {"_id": sec["_id"]},
                            {"$set": {"threshold_kwh": new_threshold}},
                        )
                        st.success("Limite atualizado!")
                        st.rerun()

        st.divider()
        st.subheader("Adicionar Novo Setor")
        with st.form("new_sector_form"):
            new_id = st.text_input("ID do setor (ex: sec_005)")
            new_name = st.text_input("Nome do setor")
            new_sensor = st.text_input("ID do sensor")
            new_threshold = st.number_input("Limite de consumo (kWh)", value=10.0)
            submitted = st.form_submit_button("Criar setor")

            if submitted and new_id and new_name:
                db.sectors.insert_one({
                    "_id": new_id,
                    "building_id": "bld_001",
                    "name": new_name,
                    "sensor_id": new_sensor,
                    "threshold_kwh": new_threshold,
                    "status": "online",
                    "last_seen": datetime.utcnow(),
                })
                st.success(f"Setor '{new_name}' criado com sucesso!")
                st.rerun()

# ---------------------------------------------------------------------------
# ABA 3: Demonstração CRUD
# ---------------------------------------------------------------------------
with tab_crud_demo:
    st.subheader("Demonstração Isolada do CRUD (MongoDB)")
    if not mongo_ok:
        st.error("⚠️ O MongoDB está desconectado.")
    else:
        db = get_database()
        st.caption("Operações isoladas na coleção 'events' usando documentos marcados com demo: true.")

        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("1️⃣ INSERT — Criar Evento Demo"):
                demo_event = {
                    "_id": f"evt_demo_{datetime.utcnow().timestamp()}",
                    "sector_id": "sec_001",
                    "session_id": "demo_session",
                    "building_id": "bld_001",
                    "event_type": "HIGH_CONSUMPTION",
                    "value_kwh": 99.9,
                    "threshold_kwh": 12.5,
                    "detected_at": datetime.utcnow(),
                    "notification": {"enabled": True, "status": "PENDING", "sent_at": None},
                    "demo": True,
                }
                db.events.insert_one(demo_event)
                st.success("Documento inserido:")
                st.json(demo_event, expanded=False)

        with col2:
            if st.button("2️⃣ FIND — Buscar Eventos Demo"):
                results = list(db.events.find({"demo": True}))
                st.write(f"Encontrados {len(results)} documento(s):")
                for r in results:
                    st.json(r, expanded=False)

        with col3:
            if st.button("3️⃣ UPDATE — Resolver Eventos Demo"):
                result = db.events.update_many(
                    {"demo": True},
                    {"$set": {"notification.status": "SENT", "notification.sent_at": datetime.utcnow()}},
                )
                st.success(f"{result.modified_count} documento(s) atualizado(s).")

        with col4:
            if st.button("4️⃣ DELETE — Limpar Eventos Demo"):
                result = db.events.delete_many({"demo": True})
                st.success(f"{result.deleted_count} documento(s) apagado(s).")

# ---------------------------------------------------------------------------
# ABA 4: Relatórios (Pipelines de Agregação MongoDB)
# ---------------------------------------------------------------------------
with tab_reports:
    st.subheader("Relatórios das Pipelines de Agregação (MongoDB)")
    if not mongo_ok:
        st.error("⚠️ O MongoDB está desconectado.")
    else:
        db = get_database()
        
        st.markdown("### 🏆 Ranking de Setores por Anomalias (Pipeline 1)")
        st.caption("Gravado via $merge na coleção `reports_sector_ranking`")
        
        # Botão para recalcular
        if st.button("🔄 Rodar Aggregations Script (Executar Pipelines)"):
            try:
                import aggregations
                aggregations.main()
                st.success("Pipelines executadas com sucesso e coleções de relatórios atualizadas!")
            except Exception as e:
                st.error(f"Erro ao executar: {e}")
        
        ranking = list(db.reports_sector_ranking.find().sort("total_events", -1))
        if not ranking:
            st.warning("Nenhum dado de relatório encontrado. Rode o script de agregações acima.")
        else:
            for r in ranking:
                severity_color = "🔴" if r.get("severity") == "ALTA" else "🟡"
                with st.container(border=True):
                    col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 1.5])
                    with col1:
                        st.markdown(f"**{r['building_name']} / {r['sector_name']}**")
                    with col2:
                        st.metric("Total de Eventos", r["total_events"])
                    with col3:
                        st.metric("Consumo Médio", f"{r['avg_consumption_kwh']} kWh")
                    with col4:
                        st.write(f"{severity_color} **{r.get('severity', 'MODERADA')}**")

        st.divider()

        st.markdown("### 📨 Fila de Notificação (Pipeline 2)")
        st.caption("Amostra aleatória de alertas pendentes gravados na coleção `reports_notification_queue`")
        queue = list(db.reports_notification_queue.find().sort("value_kwh", -1))
        if not queue:
            st.warning("Nenhum alerta na fila de notificação.")
        else:
            for q in queue:
                st.info(q["alert_message"])

# ---------------------------------------------------------------------------
# ABA 5: Redis (Sessões, Streams & Estruturas Probabilísticas)
# ---------------------------------------------------------------------------
with tab_redis:
    st.subheader("🔑 Redis — Estruturas Comuns e Probabilísticas")
    if not redis_ok:
        st.error("⚠️ O Redis está offline. Certifique-se de que o container local está rodando ou verifique as credenciais no .env.")
    else:
        r_client = get_redis()
        
        # Importa o módulo redis_funcionalidades de forma dinâmica e segura
        import redis_funcionalidades as rf

        col_red1, col_red2 = st.columns(2)
        
        with col_red1:
            st.markdown("### 👤 Sessão do Gestor (HASH + SET + STRING com TTL)")
            
            # Garante que o gestor esteja cadastrado
            gestor_id = "ecomonitor:gestor:admin"
            rf.cadastrar_gestor(r_client)
            
            # Formulário de login
            st.markdown("**Simular Login do Responsável**")
            login_username = st.text_input("Usuário", value="admin", disabled=True)
            login_password = st.text_input("Senha", value="eco123", type="password")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("Fazer Login"):
                    token = rf.fazer_login(r_client, gestor_id, login_password)
                    if token:
                        st.session_state["redis_token"] = token
                        st.success(f"Login efetuado! Token de sessão gerado.")
                    else:
                        st.error("Falha na autenticação (senha incorreta).")
            with col_b2:
                if st.button("Fazer Logout"):
                    token = st.session_state.get("redis_token")
                    if token:
                        rf.fazer_logout(r_client, token)
                        st.session_state["redis_token"] = None
                        st.info("Sessão finalizada com sucesso.")
                    else:
                        st.warning("Nenhuma sessão ativa encontrada.")
            
            # Mostra dados da sessão se houver token ativo
            token = st.session_state.get("redis_token")
            if token:
                sessao_key = f"ecomonitor:sessao:{token}"
                ttl = r_client.ttl(sessao_key)
                if ttl > 0:
                    st.success(f"Sessão válida! Token: `{token}`")
                    st.metric("TTL do Token (Redis STRING)", f"{ttl} segundos")
                    st.write(f"Sessões ativas no Redis (SET): `{r_client.scard('ecomonitor:sessoes:ativas')}`")
                else:
                    st.warning("Sessão expirou no Redis.")
                    st.session_state["redis_token"] = None
                    
        with col_red2:
            st.markdown("### 📊 Processamento de Alertas no Redis")
            
            if st.button("⚡ Simular Fluxo de Alertas (MongoDB ➡️ Redis)"):
                try:
                    # Roda a simulação integrada com o Redis
                    alertas = rf.consultar_alertas_pendentes_mongodb()
                    if not alertas:
                        st.warning("Nenhum alerta pendente no MongoDB para processar. Popule o banco primeiro!")
                    else:
                        usar_bloom = rf.bloom_disponivel(r_client)
                        enviados, ignorados = rf.enviar_alertas_para_stream(r_client, alertas, usar_bloom)
                        st.success(f"Processados {len(alertas)} alertas! Enviados ao Stream: {enviados}. Ignorados (Deduplicados): {ignorados}.")
                except Exception as e:
                    st.error(f"Erro ao processar fluxo: {e}")

            st.divider()
            
            # Métricas em Tempo Real
            col_met1, col_met2 = st.columns(2)
            with col_met1:
                total_setores = r_client.pfcount("ecomonitor:hll:setores_com_anomalia")
                st.metric("Setores com Anomalia (HyperLogLog)", total_setores)
            with col_met2:
                usar_bloom = rf.bloom_disponivel(r_client)
                modo_bloom = "Ativo (RedisBloom)" if usar_bloom else "Fallback (SET)"
                st.metric("Estrutura de Deduplicação", modo_bloom)

            st.markdown("**Leaderboard de Criticidade de Setores (ZSET)**")
            ranking = r_client.zrevrange("ecomonitor:ranking:setores", 0, -1, withscores=True)
            if not ranking:
                st.info("Nenhum setor cadastrado no ranking do Redis ainda.")
            else:
                for pos, (setor, score) in enumerate(ranking, start=1):
                    st.write(f"#{pos} Setor `{setor}`: **{int(score)} anomalias**")

        st.divider()
        st.markdown("### 📬 Fila de Notificações Ativas (Redis STREAM)")
        messages = r_client.xrevrange("ecomonitor:stream:alertas", max="+", min="-", count=10)
        if not messages:
            st.info("Fila do Stream vazia no momento.")
        else:
            for msg_id, fields in messages:
                with st.chat_message("assistant", avatar="⚡"):
                    st.markdown(f"**ID da Fila:** `{msg_id}`")
                    st.write(fields.get("message"))
                    st.caption(f"Setor ID: {fields.get('sector_id')} | Sensor: {fields.get('sensor_id')} | Detectado: {fields.get('detected_at')}")

# ---------------------------------------------------------------------------
# ABA 6: Neo4j (Grafos & GDS Degree Centrality)
# ---------------------------------------------------------------------------
with tab_neo4j:
    st.subheader("🕸️ Neo4j — Análise de Grafo e GDS (Degree Centrality)")
    if not neo4j_ok:
        st.error("⚠️ O Neo4j está offline. Certifique-se de que a instância local/AuraDB está ativa e as credenciais no .env estão corretas.")
    else:
        st.markdown("### Estrutura do Grafo de Monitoramento")
        st.code("""
(Building) -[:POSSUI]-> (Sector) -[:MONITORADO_POR]-> (Sensor)
                          (Sector) -[:GEROU]-> (Event)
        """, language="text")

        col_neo1, col_neo2 = st.columns([1, 2])
        
        with col_neo1:
            st.markdown("### 🔄 Sincronização do Grafo")
            st.caption("Limpa o grafo no Neo4j e importa os dados atualizados do MongoDB.")
            
            if st.button("🔄 Sincronizar Grafo MongoDB ➡️ Neo4j"):
                with st.spinner("Sincronizando..."):
                    try:
                        import neo4j_ecomonitor
                        buildings, sectors, events = neo4j_ecomonitor.carregar_dados_mongodb()
                        
                        g = EcoMonitorGraph()
                        g.limpar_grafo()
                        g.criar_constraints()
                        g.importar_dados(buildings, sectors, events)
                        g.close()
                        st.success("Grafo sincronizado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro na sincronização: {e}")

            # Resumo do Grafo
            st.divider()
            st.markdown("**Resumo do Grafo Atual:**")
            try:
                g = EcoMonitorGraph()
                nodes_res = g.run("MATCH (n) RETURN labels(n)[0] AS type, count(*) AS total ORDER BY type")
                rels_res = g.run("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS total ORDER BY type")
                g.close()
                
                st.write("**Nós:**")
                for n in nodes_res:
                    st.write(f"- `{n['type']}`: {n['total']}")
                    
                st.write("**Relacionamentos:**")
                for r in rels_res:
                    st.write(f"- `[:{r['type']}]`: {r['total']}")
            except Exception as e:
                st.error(f"Erro ao obter resumo: {e}")

        with col_neo2:
            st.markdown("### 🏆 Análise de Criticidade via Degree Centrality (GDS)")
            st.caption("Quantifica a criticidade dos setores baseando-se no número de conexões [:GEROU] com eventos de consumo anômalo.")
            
            if st.button("⚡ Executar Degree Centrality"):
                with st.spinner("Calculando centralidades..."):
                    try:
                        g = EcoMonitorGraph()
                        
                        # Executa Degree Centrality (com fallback Cypher se GDS não estiver disponível)
                        # O método executar_degree_centrality imprime no terminal, vamos reproduzir e ler o resultado no streamlit
                        rows = g.run("""
                            MATCH (s:Sector)
                            OPTIONAL MATCH (s)-[:GEROU]->(e:Event)
                            WITH s, count(e) AS degree_score
                            SET s.degree_score = degree_score
                            RETURN s.name AS sector, degree_score AS score
                            ORDER BY score DESC
                        """)
                        g.close()
                        
                        st.success("Cálculo finalizado!")
                        for pos, row in enumerate(rows, start=1):
                            score = int(row['score'])
                            status_text = "🔴 Alta prioridade" if score >= 5 else "🟡 Normal"
                            st.write(f"#{pos} **{row['sector']}**: {score} conexões ({status_text})")
                            
                    except Exception as e:
                        st.error(f"Erro ao executar Degree Centrality: {e}")

            st.divider()
            st.markdown("**Exemplo de Consulta Cypher para Verificar a Criticidade:**")
            st.code("""
MATCH (s:Sector)
RETURN s.name AS setor, s.degree_score AS criticidade
ORDER BY criticidade DESC;
            """, language="cypher")
