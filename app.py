import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client

# Configuração de Layout expansivo
st.set_page_config(page_title="Dashboard ANTT Monitriip", layout="wide")

# 1. Conexão estável e performática com a Nuvem do Supabase
@st.cache_data(ttl=600) # Mantém cache por 10 minutos
def carregar_dados_do_banco():
    # Suas credenciais oficiais do Supabase (mantenha as que funcionaram nos cards)
    URL = "https://czloymgdsmjysuomyvcm.supabase.co"
    KEY = "sb_publishable_QemcKKUNYxrMcqaXziH4tA_0PI2c4Ka"
    supabase = create_client(URL, KEY)
    
    lista_registros = []
    tamanho_pagina = 1000
    offset = 0
    
    # Criamos um container de aviso visual temporário para o usuário acompanhar o carregamento
    status_progresso = st.empty()
    
    # Loop de Paginação Infalível: busca dados até a API do Supabase voltar vazia
    while True:
        status_progresso.text(f"📥 Coletando dados do Supabase... Registros processados: {offset:,}".replace(",", "."))
        
        resposta = supabase.table("bilhetagem_antt").select(
            "ano_emissao_bilhete, tipo_servico, tipo_tarifa, quantidade_bilhetes, valor_total"
        ).range(offset, offset + tamanho_pagina - 1).execute()
        
        dados_pagina = resposta.data
        
        if not dados_pagina:
            break # Se a página veio vazia, significa que coletamos toda a base!
            
        lista_registros.extend(dados_pagina)
        offset += tamanho_pagina
        
        # Trava de segurança para portfólio (limita a busca em lotes para evitar estouro de RAM no Streamlit)
        if offset >= 1500000: 
            break
            
    # Limpa a mensagem de progresso após concluir
    status_progresso.empty()
    
    df = pd.DataFrame(lista_registros)
    df['data_txt'] = df['ano_emissao_bilhete'].astype(str)
    return df

with st.spinner("Conectando ao banco de dados Supabase e quebrando limites de paginação..."):
    df = carregar_dados_do_banco()

st.title("📊 Painel Estratégico de Vendas e Rotas (Supabase Cloud)")
st.markdown(f"**Registros processados via API:** {len(df):,}".replace(",", "."))
st.markdown("---")

# ==========================================
# 2. BARRA LATERAL DE FILTROS (SIDEBAR)
# ==========================================
st.sidebar.header("Filtros do Painel")

tarifas_disponiveis = sorted(df['tipo_tarifa'].dropna().unique().astype(str))
tarifas_selecionadas = st.sidebar.multiselect("Tipo de Tarifa:", options=tarifas_disponiveis, default=tarifas_disponiveis)

servicos_disponiveis = sorted(df['tipo_servico'].dropna().unique().astype(str))
servicos_selecionados = st.sidebar.multiselect("Tipo de Serviço:", options=servicos_disponiveis, default=servicos_disponiveis)

df_filtrado = df[
    (df['tipo_tarifa'].astype(str).isin(tarifas_selecionadas)) &
    (df['tipo_servico'].astype(str).isin(servicos_selecionados))
].copy()

# ==========================================
# 3. CARDS KPI (MÉTRICAS)
# ==========================================
total_bilhetes = int(df_filtrado['quantidade_bilhetes'].sum()) if not df_filtrado.empty else 0
faturamento_total = float(df_filtrado['valor_total'].sum()) if not df_filtrado.empty else 0.0
ticket_medio = faturamento_total / total_bilhetes if total_bilhetes > 0 else 0.0

txt_total_bilhetes = f"{total_bilhetes:,}".replace(",", ".")
txt_faturamento_total = f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
txt_ticket_medio = f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("Total de Bilhetes Emitidos", txt_total_bilhetes)
with kpi2:
    st.metric("Faturamento Total", txt_faturamento_total)
with kpi3:
    st.metric("Ticket Médio Geral", txt_ticket_medio)

st.markdown("---")

# ==========================================
# 4. GRÁFICOS E VISUALIZAÇÕES
# ==========================================
if not df_filtrado.empty:
    st.subheader("📈 Evolução Temporal: Bilhetes vs Faturamento")

    df_temporal = df_filtrado.groupby('data_txt').agg(
        total_bilhetes=('quantidade_bilhetes', 'sum'),
        total_faturamento=('valor_total', 'sum')
    ).reset_index().sort_values('data_txt')

    fig_temporal = go.Figure()
    fig_temporal.add_trace(go.Bar(
        x=df_temporal['data_txt'], y=df_temporal['total_bilhetes'], 
        name="Bilhetes Emitidos", yaxis="y", marker_color='#1f77b4'
    ))
    fig_temporal.add_trace(go.Scatter(
        x=df_temporal['data_txt'], y=df_temporal['total_faturamento'], 
        name="Faturamento (R$)", yaxis="y2", mode='lines+markers', line=dict(color='#ff7f0e', width=3)
    ))
    
    fig_temporal.update_layout(
        yaxis=dict(title="Quantidade de Bilhetes", title_font_color='#1f77b4', tickfont=dict(color='#1f77b4')),
        yaxis2=dict(title="Faturamento (R$)", title_font_color='#ff7f0e', tickfont=dict(color='#ff7f0e'), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99), hovermode="x unified", margin=dict(l=40, r=40, t=20, b=40)
    )
    st.plotly_chart(fig_temporal, use_container_width=True)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚌 Participação dos Serviços no Faturamento")
        df_servico = df_filtrado.groupby('tipo_servico', observed=False).agg(
            Faturamento=('valor_total', 'sum')
        ).reset_index()
        fig_servico = px.pie(df_servico, values='Faturamento', names='tipo_servico', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_servico, use_container_width=True)

    with col2:
        st.subheader("🎟️ Participação por Tipo de Tarifa")
        df_tarifa = df_filtrado.groupby('tipo_tarifa', observed=False)['quantidade_bilhetes'].sum().reset_index()
        fig_tarifa = px.pie(df_tarifa, values='quantidade_bilhetes', names='tipo_tarifa', color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_tarifa, use_container_width=True)
else:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados.")
