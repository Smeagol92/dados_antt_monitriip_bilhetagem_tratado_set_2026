import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuração de Layout da Página
st.set_page_config(layout="wide", page_title="Dashboard ANTT Monitriip", page_icon="🚌")

# ==========================================
# 1. CARREGAMENTO DOS DADOS (URL REAL RAW CORRIGIDA)
# ==========================================
@st.cache_data
def load_all_data():
    # URL Raw oficial apontando diretamente para a pasta 'data' do seu repositório
    base_raw_url = "https://githubusercontent.com"
    
    arquivos = {
        "geral": "tabela_data_viagem_geral.csv",
        "destino_uf": "tabela_ponto_destino_viagem_uf.csv",
        "origem_uf": "tabela_ponto_origem_viagem_uf.csv",
        "rota_unica": "tabela_rota_unica.csv",
        "tarifa": "tabela_tipo_tarifa.csv",
        "nacionalidade": "tabela_nacional_internacional.csv",
        "antecedencia": "tabela_meses_antecedencia.csv",
        "ambito": "tabela_estadual_interestadual.csv",
        "gratuidade": "tabela_tipo_gratuidade.csv",
        "servico": "tabela_tipo_servico.csv"
    }
    
    dfs = {}
    for key, filename in arquivos.items():
        url = base_raw_url + filename
        dfs[key] = pd.read_csv(url, sep=";")
        dfs[key]['data_viagem_dt'] = pd.to_datetime(dfs[key]['data_viagem'], format='%Y-%m')
        
    return dfs

# Carrega todas as bases de dados mapeadas
try:
    dfs = load_all_data()
except Exception as e:
    st.error(f"Erro de conexão ou estrutura ao carregar arquivos do GitHub: {e}")
    st.stop()

# ==========================================
# 2. SELETORES DO MENU LATERAL (FILTROS)
# ==========================================
st.sidebar.header("Filtros do Dashboard")

# Filtro de Data Dinâmico baseado no histórico geral
todas_datas = sorted(dfs["geral"]['data_viagem_dt'].unique())
opcoes_datas_str = [d.strftime('%m/%Y') for d in todas_datas]

data_inicio_str = st.sidebar.selectbox("Data Início", opcoes_datas_str, index=0)
data_fim_str = st.sidebar.selectbox("Data Fim", opcoes_datas_str, index=len(opcoes_datas_str)-1)

data_inicio_dt = pd.to_datetime(data_inicio_str, format='%m/%Y')
data_fim_dt = pd.to_datetime(data_fim_str, format='%m/%Y')

if data_inicio_dt > data_fim_dt:
    st.sidebar.error("A Data Início não pode ser posterior à Data Fim.")
    st.stop()

# Opções para os filtros adicionais baseados nos dados reais
filtro_ambito = st.sidebar.multiselect("Âmbito da Viagem", options=dfs["ambito"]["estadual_interestadual"].unique())
filtro_antecedencia = st.sidebar.multiselect("Meses de Antecedência", options=sorted(dfs["antecedencia"]["meses_antecedencia"].unique()))
filtro_nacionalidade = st.sidebar.multiselect("Nacionalidade", options=dfs["nacionalidade"]["nacional_internacional"].unique())
filtro_origem = st.sidebar.multiselect("UF de Origem", options=sorted(dfs["origem_uf"]["ponto_origem_viagem_uf"].astype(str).unique()))
filtro_destino = st.sidebar.multiselect("UF de Destino", options=sorted(dfs["destino_uf"]["ponto_destino_viagem_uf"].astype(str).unique()))
filtro_gratuidade = st.sidebar.multiselect("Tipo de Gratuidade", options=dfs["gratuidade"]["tipo_gratuidade"].unique())
filtro_servico = st.sidebar.multiselect("Tipo de Serviço", options=dfs["servico"]["tipo_servico"].unique())
filtro_tarifa = st.sidebar.multiselect("Tipo de Tarifa", options=dfs["tarifa"]["tipo_tarifa"].unique())

# ==========================================
# 3. FILTRAGEM TEMPORAL DOS DATAFRAMES
# ==========================================
dfs_f = {}
for key, df in dfs.items():
    mask = (df['data_viagem_dt'] >= data_inicio_dt) & (df['data_viagem_dt'] <= data_fim_dt)
    dfs_f[key] = df[mask].copy()

# ==========================================
# 4. LÓGICA DE FILTRAGEM CRUZADA EM TEMPO REAL
# ==========================================
datas_validas = set(dfs_f["geral"]["data_viagem"])

if filtro_ambito:
    dfs_f["ambito"] = dfs_f["ambito"][dfs_f["ambito"]["estadual_interestadual"].isin(filtro_ambito)]
    datas_validas &= set(dfs_f["ambito"]["data_viagem"])
if filtro_antecedencia:
    dfs_f["antecedencia"] = dfs_f["antecedencia"][dfs_f["antecedencia"]["meses_antecedencia"].isin(filtro_antecedencia)]
    datas_validas &= set(dfs_f["antecedencia"]["data_viagem"])
if filtro_nacionalidade:
    dfs_f["nacionalidade"] = dfs_f["nacionalidade"][dfs_f["nacionalidade"]["nacional_internacional"].isin(filtro_nacionalidade)]
    datas_validas &= set(dfs_f["nacionalidade"]["data_viagem"])
if filtro_origem:
    dfs_f["origem_uf"] = dfs_f["origem_uf"][dfs_f["origem_uf"]["ponto_origem_viagem_uf"].isin(filtro_origem)]
    datas_validas &= set(dfs_f["origem_uf"]["data_viagem"])
if filtro_destino:
    dfs_f["destino_uf"] = dfs_f["destino_uf"][dfs_f["destino_uf"]["ponto_destino_viagem_uf"].isin(filtro_destino)]
    datas_validas &= set(dfs_f["destino_uf"]["data_viagem"])
if filtro_gratuidade:
    dfs_f["gratuidade"] = dfs_f["gratuidade"][dfs_f["gratuidade"]["tipo_gratuidade"].isin(filtro_gratuidade)]
    datas_validas &= set(dfs_f["gratuidade"]["data_viagem"])
if filtro_servico:
    dfs_f["servico"] = dfs_f["servico"][dfs_f["servico"]["tipo_servico"].isin(filtro_servico)]
    datas_validas &= set(dfs_f["servico"]["data_viagem"])
if filtro_tarifa:
    dfs_f["tarifa"] = dfs_f["tarifa"][dfs_f["tarifa"]["tipo_tarifa"].isin(filtro_tarifa)]
    datas_validas &= set(dfs_f["tarifa"]["data_viagem"])

# Aplicando as datas válidas resultantes do cruzamento de filtros
df_g_kpi = dfs_f["geral"][dfs_f["geral"]["data_viagem"].isin(datas_validas)]

# ==========================================
# 5. CARDS DE INDICADORES (KPIs)
# ==========================================
total_bilhetes = df_g_kpi["total_bilhetes"].sum() if not df_g_kpi.empty else 0
total_arrecadacao = df_g_kpi["total_arrecadacao"].sum() if not df_g_kpi.empty else 0
ticket_medio = total_arrecadacao / total_bilhetes if total_bilhetes > 0 else 0

# Taxa de aquisição em cima da hora (Meses Antecedência = 0)
df_ant = dfs_f["antecedencia"]
if not df_ant.empty:
    df_ant_kpi = df_ant[df_ant["data_viagem"].isin(datas_validas)]
    total_ant = df_ant_kpi["total_bilhetes"].sum()
    cima_hora = df_ant_kpi[df_ant_kpi["meses_antecedencia"] == 0]["total_bilhetes"].sum()
    pct_cima_hora = (cima_hora / total_ant * 100) if total_ant > 0 else 0
else:
    pct_cima_hora = 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Soma de Bilhetes", f"{total_bilhetes:,.0f}".replace(",", "."))
kpi2.metric("Faturamento Geral", f"R$ {total_arrecadacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
kpi3.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
kpi4.metric("Compras em Cima da Hora (Mês 0)", f"{pct_cima_hora:.2f}%")

st.markdown("---")

# ==========================================
# 6. RENDERIZAÇÃO DOS GRÁFICOS
# ==========================================
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("📈 Linha do Tempo: Bilhetes Emitidos vs Faturamento Arrecadado")
    df_ev_base = dfs_f["geral"][dfs_f["geral"]["data_viagem"].isin(datas_validas)]
    if not df_ev_base.empty:
        df_ev = df_ev_base.groupby("data_viagem").agg({"total_bilhetes": "sum", "total_arrecadacao": "sum"}).reset_index()
        fig_ev = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ev.add_trace(go.Bar(x=df_ev["data_viagem"], y=df_ev["total_bilhetes"], name="Bilhetes", marker_color="#1D3557"), secondary_y=False)
        fig_ev.add_trace(go.Scatter(x=df_ev["data_viagem"], y=df_ev["total_arrecadacao"], name="Faturamento", line=dict(color="#E63946", width=3)), secondary_y=True)
        fig_ev.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_ev, use_container_width=True)
    else:
        st.info("Sem registros para o intervalo de tempo e filtros selecionados.")

with col_g2:
    st.subheader("🚌 Top 10 Rotas Únicas com Maior Fluxo")
    df_rotas = dfs_f["rota_unica"][dfs_f["rota_unica"]["data_viagem"].isin(datas_validas)]
    if not df_rotas.empty:
        df_rt_g = df_rotas.groupby("rota_unica")["total_bilhetes"].sum().reset_index()
        df_rt_g = df_rt_g.sort_values(by="total_bilhetes", ascending=True).tail(10)
        fig_rt = px.bar(df_rt_g, x="total_bilhetes", y="rota_unica", orientation="h", color_discrete_sequence=["#457B9D"])
        st.plotly_chart(fig_rt, use_container_width=True)
    else:
        st.info("Sem registros de rotas para o período e filtros atuais.")

st.markdown("---")
col_g3, col_g4, col_g5 = st.columns(3)

with col_g3:
    st.subheader("🎫 Divisão por Tipo de Tarifa")
    df_tf = dfs_f["tarifa"][dfs_f["tarifa"]["data_viagem"].isin(datas_validas)]
    if not df_tf.empty:
        df_tf_g = df_tf.groupby("tipo_tarifa")["total_bilhetes"].sum().reset_index()
        fig_tf = px.pie(df_tf_g, values="total_bilhetes", names="tipo_tarifa", hole=0.3, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_tf.update_layout(legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_tf, use_container_width=True)
    else:
        st.info("Sem dados disponíveis para tipos de tarifa.")

with col_g4:
    st.subheader("🌎 Proporção de Nacionalidade")
    df_nac = dfs_f["nacionalidade"][dfs_f["nacionalidade"]["data_viagem"].isin(datas_validas)]
    if not df_nac.empty:
        df_nac_g = df_nac.groupby("nacional_internacional")["total_bilhetes"].sum().reset_index()
        fig_nac = px.pie(df_nac_g, values="total_bilhetes", names="nacional_internacional", hole=0.3, color_discrete_sequence=["#2A9D8F", "#E76F51"])
        fig_nac.update_layout(legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_nac, use_container_width=True)
    else:
        st.info("Sem dados disponíveis para nacionalidade.")

with col_g5:
    st.subheader("📍 Participação por Estado (Destino)")
    df_dest = dfs_f["destino_uf"][dfs_f["destino_uf"]["data_viagem"].isin(datas_validas)]
    if not df_dest.empty:
        df_dst_g = df_dest.groupby("ponto_destino_viagem_uf")["total_bilhetes"].sum().reset_index()
        df_dst_g = df_dst_g.sort_values(by="total_bilhetes", ascending=False).head(10)
        fig_dest = px.bar(df_dst_g, x="ponto_destino_viagem_uf", y="total_bilhetes", color_discrete_sequence=["#F4A261"])
        st.plotly_chart(fig_dest, use_container_width=True)
    else:
        st.info("Sem dados disponíveis para os estados de destino.")
