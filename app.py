import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# Configuração de Layout expansivo
st.set_page_config(page_title="Dashboard ANTT Monitriip", layout="wide")

# 1. Carregamento Inteligente e 100% Local (Sem chamadas HTTP/URLs de internet)
@st.cache_data
def carregar_dados_otimizado():
    colunas_necessarias = [
        'data_emissao_bilhete', 'rota_unica', 'tipo_servico',
        'quantidade_bilhetes', 'valor_total', 'tipo_tarifa', 'meses_antecedencia'
    ]
    
    lista_dataframes = []
    
    # Loop para ler os 20 arquivos locais diretamente da pasta do projeto
    for i in range(20):
        caminho_local = f"data/dados_parte_{i}.parquet"
        
        # Proteção robusta: verifica se o arquivo realmente existe fisicamente no repositório antes de ler
        if not os.path.exists(caminho_local):
            st.error(f"❌ Erro Crítico: O arquivo '{caminho_local}' não foi encontrado na estrutura do repositório.")
            st.info("Por favor, verifique se o arquivo foi incluído e enviado corretamente na pasta 'data' do GitHub.")
            st.stop()
            
        try:
            df_parte = pd.read_parquet(
                caminho_local,
                engine="pyarrow",
                columns=colunas_necessarias
            )
            
            # Garante que dados parciais tenham o tamanho correto de arquivo binário
            if df_parte.empty:
                st.warning(f"⚠️ O arquivo {caminho_local} foi lido, mas está totalmente vazio.")
                
            lista_dataframes.append(df_parte)
        except Exception as e:
            st.error(f"❌ Erro Crítico ao processar a partição local: {caminho_local}")
            st.exception(e)
            st.stop()
            
    # Combina as partições carregadas localmente
    df = pd.concat(lista_dataframes, ignore_index=True)
    
    # Conversões primitivas para estabilização de tipos de dados
    df['quantidade_bilhetes'] = df['quantidade_bilhetes'].astype(int)
    df['valor_total'] = df['valor_total'].astype(float)
    df['meses_antecedencia'] = df['meses_antecedencia'].astype(int)
    df['data_txt'] = df['data_emissao_bilhete'].astype(str)
    
    return df

with st.spinner("Construindo e otimizando a base de dados ANTT/Monitriip local..."):
    df = carregar_dados_otimizado()

st.title("📊 Painel Estratégico de Vendas e Rotas")
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

if not df_filtrado.empty:
    bilhetes_cima_hora = df_filtrado[df_filtrado['meses_antecedencia'] == 0]['quantidade_bilhetes'].sum()
    pct_cima_hora = (bilhetes_cima_hora / total_bilhetes) * 100 if total_bilhetes > 0 else 0.0
else:
    pct_cima_hora = 0.0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("Total de Bilhetes Emitidos", f"{total_bilhetes:,}".replace(",", "."))
with kpi2:
    st.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
with kpi3:
    st.metric("Ticket Médio Geral", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
with kpi4:
    st.metric("Compras em Cima da Hora", f"{pct_cima_hora:.1f}%")

st.markdown("---")

# ==========================================
# 4. GRÁFICOS E VISUALIZAÇÕES
# ==========================================
if not df_filtrado.empty:
    st.subheader("📈 Evolução Temporal: Bilhetes vs Faturamento")
    visao_temporal = st.radio("Agrupar gráfico por:", options=["Ano", "Mês", "Dia"], index=1, horizontal=True)

    df_temp_temporal = df_filtrado[['data_txt', 'quantidade_bilhetes', 'valor_total']].copy()

    if visao_temporal == "Ano":
        df_temp_temporal['periodo'] = df_temp_temporal['data_txt'].str[:4]
    elif visao_temporal == "Mês":
        df_temp_temporal['periodo'] = df_temp_temporal['data_txt'].str[:7]
    else:
        df_temp_temporal['periodo'] = df_temp_temporal['data_txt'].str[:10]

    df_temporal = df_temp_temporal.groupby('periodo').agg(
        total_bilhetes=('quantidade_bilhetes', 'sum'),
        total_faturamento=('valor_total', 'sum')
    ).reset_index().sort_values('periodo')

    fig_temporal = go.Figure()
    fig_temporal.add_trace(go.Bar(x=df_temporal['periodo'], y=df_temporal['total_bilhetes'], name="Bilhetes Emitidos", yaxis="y", marker_color='#1f77b4'))
    fig_temporal.add_trace(go.Scatter(x=df_temporal['periodo'], y=df_temporal['total_faturamento'], name="Faturamento (R$)", yaxis="y2", mode='lines+markers', line=dict(color='#ff7f0e', width=3)))
    fig_temporal.update_layout(
        yaxis=dict(title="Quantidade de Bilhetes", titlefont=dict(color='#1f77b4'), tickfont=dict(color='#1f77b4')),
        yaxis2=dict(title="Faturamento (R$)", titlefont=dict(color='#ff7f0e'), tickfont=dict(color='#ff7f0e'), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99), hovermode="x unified", margin=dict(l=40, r=40, t=20, b=40)
    )
    st.plotly_chart(fig_temporal, use_container_width=True)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏆 Top 10 Linhas Mais Movimentadas")
        top_linhas = df_filtrado.groupby('rota_unica')['quantidade_bilhetes'].sum().reset_index()
        top_linhas = top_linhas.sort_values(by='quantidade_bilhetes', ascending=False).head(10)
        fig_linhas = px.bar(top_linhas, x='quantidade_bilhetes', y='rota_unica', orientation='h', color_discrete_sequence=['#2ca02c'])
        fig_linhas.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_linhas, use_container_width=True)

    with col2:
        st.subheader("🚌 Participação dos Serviços no Faturamento e Bilhetagem")
        df_servico = df_filtrado.groupby('tipo_servico', observed=False).agg(
            Bilhetes=('quantidade_bilhetes', 'sum'), Faturamento=('valor_total', 'sum')
        ).reset_index()
        visao_servico = st.radio("Visualizar Participação por:", ["Faturamento", "Bilhetes"], horizontal=True, key="servico_radio")
        fig_servico = px.pie(df_servico, values=visao_servico, names='tipo_servico', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_servico, use_container_width=True)

    st.markdown("---")

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("🎟️ Participação por Tipo de Tarifa")
        df_tarifa = df_filtrado.groupby('tipo_tarifa', observed=False)['quantidade_bilhetes'].sum().reset_index()
        fig_tarifa = px.pie(df_tarifa, values='quantidade_bilhetes', names='tipo_tarifa', color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_tarifa, use_container_width=True)

    with col4:
        st.subheader("📋 Lista de Detalhamento das Rotas")
        df_detalhe_rotas = df_filtrado.groupby('rota_unica').agg(
            Bilhetes_Emitidos=('quantidade_bilhetes', 'sum'), Faturamento_Total=('valor_total', 'sum')
        ).reset_index()
        df_detalhe_rotas['Ticket_Médio'] = df_detalhe_rotas['Faturamento_Total'] / df_detalhe_rotas['Bilhetes_Emitidos']
        df_detalhe_rotas = df_detalhe_rotas.sort_values(by='Faturamento_Total', ascending=False)
        st.dataframe(
            df_detalhe_rotas,
            column_config={
                "rota_unica": "Rota Única",
                "Bilhetes_Emitidos": st.column_config.NumberColumn("Bilhetes Emitidos", format="%d"),
                "Faturamento_Total": st.column_config.NumberColumn("Faturamento Total", format="R$ %.2f"),
                "Ticket_Médio": st.column_config.NumberColumn("Ticket Médio por Rota", format="R$ %.2f")
            },
            hide_index=True, use_container_width=True
        )
else:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados na barra lateral.")
