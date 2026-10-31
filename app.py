import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página para aproveitar toda a largura da tela
st.set_page_config(page_title="Dashboard de Bilhetagem e Faturamento", layout="wide")

# 1. Carregamento Inteligente por Fragmentos Locais (20 Partições)
@st.cache_data
def carregar_dados_otimizado():
    colunas_necessarias = [
        'data_emissao_bilhete', 'rota_unica', 'tipo_servico',
        'quantidade_bilhetes', 'valor_total', 'tipo_tarifa', 'meses_antecedencia'
    ]
    
    lista_dataframes = []
    
    # Loop para ler cada uma das 20 partes (de 0 a 19)
    for i in range(20):
        caminho_arquivo = f"data/dados_parte_{i}.parquet"
        try:
            df_parte = pd.read_parquet(
                caminho_arquivo,
                engine="pyarrow",
                columns=colunas_necessarias
            )
            lista_dataframes.append(df_parte)
        except Exception as e:
            st.error(f"Erro crítico ao tentar ler o arquivo: {caminho_arquivo}")
            st.info("Dica: Certifique-se de re-subir este arquivo específico no GitHub, pois ele pode estar corrompido ou zerado.")
            st.exception(e)
            st.stop()
            
    # Concatena todas as partes de volta em um único DataFrame unificado
    df = pd.concat(lista_dataframes, ignore_index=True)
    
    df['data_emissao_bilhete'] = pd.to_datetime(df['data_emissao_bilhete'])
    
    return df

# Exibe animação de loading na primeira execução
with st.spinner("Reunindo fragmentos da base de dados estratégica..."):
    df = carregar_dados_otimizado()

st.title("📊 Painel Estratégico de Vendas e Rotas")
st.markdown("---")

# ==========================================
# 2. BARRA LATERAL DE FILTROS (SIDEBAR)
# ==========================================
st.sidebar.header("Filtros do Painel")

# Filtro por Tipo de Tarifa
tarifas_disponiveis = sorted(df['tipo_tarifa'].dropna().unique())
tarifas_selecionadas = st.sidebar.multiselect(
    "Tipo de Tarifa:", 
    options=tarifas_disponiveis, 
    default=tarifas_disponiveis
)

# Filtro por Tipo de Serviço
servicos_disponiveis = sorted(df['tipo_servico'].dropna().unique())
servicos_selecionados = st.sidebar.multiselect(
    "Tipo de Serviço:", 
    options=servicos_disponiveis, 
    default=servicos_disponiveis
)

# Aplicando os filtros de forma performática
df_filtrado = df[
    (df['tipo_tarifa'].isin(tarifas_selecionadas)) &
    (df['tipo_servico'].isin(servicos_selecionados))
].copy()

# ==========================================
# 3. CARDS KPI (MÉTRICAS)
# ==========================================
total_bilhetes = int(df_filtrado['quantidade_bilhetes'].sum()) if not df_filtrado.empty else 0
faturamento_total = float(df_filtrado['valor_total'].sum()) if not df_filtrado.empty else 0.0

# Cálculo do Ticket Médio Geral
ticket_medio = faturamento_total / total_bilhetes if total_bilhetes > 0 else 0.0

# Porcentagem de compras em cima da hora (meses_antecedencia == 0)
if not df_filtrado.empty:
    bilhetes_cima_hora = df_filtrado[df_filtrado['meses_antecedencia'] == 0]['quantidade_bilhetes'].sum()
    pct_cima_hora = (bilhetes_cima_hora / total_bilhetes) * 100 if total_bilhetes > 0 else 0.0
else:
    pct_cima_hora = 0.0

# Formatação segura para Strings antes do uso do .replace
txt_total_bilhetes = f"{total_bilhetes:,}".replace(",", ".")
txt_faturamento_total = f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
txt_ticket_medio = f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
txt_cima_hora = f"{pct_cima_hora:.1f}%"

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric("Total de Bilhetes Emitidos", txt_total_bilhetes)
with kpi2:
    st.metric("Faturamento Total", txt_faturamento_total)
with kpi3:
    st.metric("Ticket Médio Geral", txt_ticket_medio)
with kpi4:
    st.metric("Compras em Cima da Hora", txt_cima_hora)

st.markdown("---")

# ==========================================
# 4. GRÁFICOS E VISUALIZAÇÕES
# ==========================================

if not df_filtrado.empty:
    # Bloco 1: Evolução Temporal Alternável (Ano / Mês / Dia)
    st.subheader("📈 Evolução Temporal: Bilhetes vs Faturamento")

    visao_temporal = st.radio(
        "Agrupar gráfico por:",
        options=["Ano", "Mês", "Dia"],
        index=1,
        horizontal=True
    )

    df_temp_temporal = df_filtrado.copy()

    if visao_temporal == "Ano":
        df_temp_temporal['periodo'] = df_temp_temporal['data_emissao_bilhete'].dt.to_period('Y')
    elif visao_temporal == "Mês":
        df_temp_temporal['periodo'] = df_temp_temporal['data_emissao_bilhete'].dt.to_period('M')
    else:
        df_temp_temporal['periodo'] = df_temp_temporal['data_emissao_bilhete'].dt.date

    df_temporal = df_temp_temporal.groupby('periodo').agg(
        total_bilhetes=('quantidade_bilhetes', 'sum'),
        total_faturamento=('valor_total', 'sum')
    ).reset_index().sort_values('periodo')

    # CORREÇÃO CRÍTICA CONTRA TYPEERROR: Converte o eixo temporal para string explicita antes do Plotly
    df_temporal['periodo'] = df_temporal['periodo'].astype(str)

    fig_temporal = go.Figure()
    fig_temporal.add_trace(go.Bar(
        x=df_temporal['periodo'], y=df_temporal['total_bilhetes'],
        name="Bilhetes Emitidos", yaxis="y", marker_color='#1f77b4'
    ))
    fig_temporal.add_trace(go.Scatter(
        x=df_temporal['periodo'], y=df_temporal['total_faturamento'],
        name="Faturamento (R$)", yaxis="y2", mode='lines+markers', line=dict(color='#ff7f0e', width=3)
    ))
    fig_temporal.update_layout(
        yaxis=dict(title="Quantidade de Bilhetes", titlefont=dict(color='#1f77b4'), tickfont=dict(color='#1f77b4')),
        yaxis2=dict(title="Faturamento (R$)", titlefont=dict(color='#ff7f0e'), tickfont=dict(color='#ff7f0e'), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=20, b=40)
    )
    st.plotly_chart(fig_temporal, use_container_width=True)

    st.markdown("---")

    # Bloco 2: Linhas Movimentadas e Distribuição por Serviço
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏆 Top 10 Linhas Mais Movimentadas")
        top_linhas = df_filtrado.groupby('rota_unica')['quantidade_bilhetes'].sum().reset_index()
        top_linhas = top_linhas.sort_values(by='quantidade_bilhetes', ascending=False).head(10)
        
        fig_linhas = px.bar(
            top_linhas, x='quantidade_bilhetes', y='rota_unica', orientation='h',
            labels={'quantidade_bilhetes': 'Bilhetes', 'rota_unica': 'Rota/Linha'},
            color_discrete_sequence=['#2ca02c']
        )
        fig_linhas.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_linhas, use_container_width=True)

    with col2:
        st.subheader("🚌 Participação dos Serviços no Faturamento e Bilhetagem")
        df_servico = df_filtrado.groupby('tipo_servico').agg(
            Bilhetes=('quantidade_bilhetes', 'sum'),
            Faturamento=('valor_total', 'sum')
        ).reset_index()
        
        visao_servico = st.radio("Visualizar Participação por:", ["Faturamento", "Bilhetes"], horizontal=True, key="servico_radio")
        
        fig_servico = px.pie(
            df_servico, values=visao_servico, names='tipo_servico',
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_servico, use_container_width=True)

    st.markdown("---")

    # Bloco 3: Tipo de Tarifa e Detalhamento de Rotas
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("🎟️ Participação por Tipo de Tarifa")
        df_tarifa = df_filtrado.groupby('tipo_tarifa')['quantidade_bilhetes'].sum().reset_index()
        fig_tarifa = px.pie(
            df_tarifa, values='quantidade_bilhetes', names='tipo_tarifa',
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        st.plotly_chart(fig_tarifa, use_container_width=True)

    with col4:
        st.subheader("📋 Lista de Detalhamento das Rotas")
        df_detalhe_rotas = df_filtrado.groupby('rota_unica').agg(
            Bilhetes_Emitidos=('quantidade_bilhetes', 'sum'),
            Faturamento_Total=('valor_total', 'sum')
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
            hide_index=True,
            use_container_width=True
        )
else:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados na barra lateral. Altere os filtros para renderizar os gráficos.")
