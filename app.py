import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página para aproveitar toda a largura da tela
st.set_page_config(page_title="Dashboard de Bilhetagem e Faturamento", layout="wide")

# 1. Carregamento Inteligente e de Baixo Consumo de Memória
@st.cache_data
def carregar_dados_otimizado():
    colunas_necessarias = [
        'data_emissao_bilhete', 'rota_unica', 'tipo_servico',
        'quantidade_bilhetes', 'valor_total', 'tipo_tarifa', 'meses_antecedencia'
    ]
    
    lista_dataframes = []
    
    # Carrega as 20 partições diminuindo o consumo de RAM em cada uma
    for i in range(20):
        caminho_arquivo = f"data/dados_parte_{i}.parquet"
        try:
            df_parte = pd.read_parquet(
                caminho_arquivo,
                engine="pyarrow",
                columns=colunas_necessarias
            )
            
            # OTIMIZAÇÃO DE MEMÓRIA: Downcast de tipos primitivos pesados
            if 'quantidade_bilhetes' in df_parte.columns:
                df_parte['quantidade_bilhetes'] = pd.to_numeric(df_parte['quantidade_bilhetes'], downcast='integer')
            if 'valor_total' in df_parte.columns:
                df_parte['valor_total'] = pd.to_numeric(df_parte['valor_total'], downcast='float')
            if 'meses_antecedencia' in df_parte.columns:
                df_parte['meses_antecedencia'] = pd.to_numeric(df_parte['meses_antecedencia'], downcast='integer')
                
            # Converter textos repetitivos em categorias (economiza até 80% de RAM em strings)
            for col in ['tipo_servico', 'tipo_tarifa']:
                if col in df_parte.columns:
                    df_parte[col] = df_parte[col].astype('category')
                    
            lista_dataframes.append(df_parte)
        except Exception as e:
            st.error(f"Erro crítico no arquivo: {caminho_arquivo}")
            st.stop()
            
    df = pd.concat(lista_dataframes, ignore_index=True)
    del lista_dataframes # Remove referência da lista antiga imediatamente da memória
    
    # Tratamento seguro da data para timestamp
    try:
        df['data_emissao_bilhete'] = df['data_emissao_bilhete'].dt.to_timestamp()
    except:
        df['data_emissao_bilhete'] = pd.to_datetime(df['data_emissao_bilhete'], errors='coerce')
        
    return df

# Execução do carregamento leve
with st.spinner("Reunindo e otimizando base de dados estratégica..."):
    df = carregar_dados_otimizado()

st.title("📊 Painel Estratégico de Vendas e Rotas")
st.markdown("---")

# ==========================================
# 2. BARRA LATERAL DE FILTROS (SIDEBAR)
# ==========================================
st.sidebar.header("Filtros do Painel")

# Coleta os elementos únicos convertendo de categoria para texto simples na listagem
tarifas_disponiveis = sorted(df['tipo_tarifa'].dropna().unique().astype(str))
tarifas_selecionadas = st.sidebar.multiselect("Tipo de Tarifa:", options=tarifas_disponiveis, default=tarifas_disponiveis)

servicos_disponiveis = sorted(df['tipo_servico'].dropna().unique().astype(str))
servicos_selecionados = st.sidebar.multiselect("Tipo de Serviço:", options=servicos_disponiveis, default=servicos_disponiveis)

# Aplicação performática do filtro
df_filtrado = df[
    (df['tipo_tarifa'].isin(tarifas_selecionadas)) &
    (df['tipo_servico'].isin(servicos_selecionados))
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
    # Bloco 1: Evolução Temporal Alternável
    st.subheader("📈 Evolução Temporal: Bilhetes vs Faturamento")
    visao_temporal = st.radio("Agrupar gráfico por:", options=["Ano", "Mês", "Dia"], index=1, horizontal=True)

    df_temp_temporal = df_filtrado[['data_emissao_bilhete', 'quantidade_bilhetes', 'valor_total']].copy()

    if visao_temporal == "Ano":
        df_temp_temporal['periodo'] = df_temp_temporal['data_emissao_bilhete'].dt.to_period('Y').astype(str)
    elif visao_temporal == "Mês":
        df_temp_temporal['periodo'] = df_temp_temporal['data_emissao_bilhete'].dt.to_period('M').astype(str)
    else:
        df_temp_temporal['periodo'] = df_temp_temporal['data_emissao_bilhete'].dt.date.astype(str)

    df_temporal = df_temp_temporal.groupby('periodo').agg(
        total_bilhetes=('quantidade_bilhetes', 'sum'),
        total_faturamento=('valor_total', 'sum')
    ).reset_index()

    fig_temporal = go.Figure()
    fig_temporal.add_trace(go.Bar(x=df_temporal['periodo'], y=df_temporal['total_bilhetes'], name="Bilhetes Emitidos", yaxis="y", marker_color='#1f77b4'))
    fig_temporal.add_trace(go.Scatter(x=df_temporal['periodo'], y=df_temporal['total_faturamento'], name="Faturamento (R$)", yaxis="y2", mode='lines+markers', line=dict(color='#ff7f0e', width=3)))
    fig_temporal.update_layout(
        yaxis=dict(title="Quantidade de Bilhetes", titlefont=dict(color='#1f77b4'), tickfont=dict(color='#1f77b4')),
        yaxis2=dict(title="Faturamento (R$)", titlefont=dict(color='#ff7f0e'), tickfont=dict(color='#ff7f0e'), overlaying="y", side="right"),
        legend=dict(x=0.01, y=0.99), hovermode="x unified", margin=dict(l=40, r=40, t=20, b=40)
    )
    st.plotly_chart(fig_temporal, use_container_width=True)
    del df_temp_temporal, df_temporal  # Liberação explícita de memória RAM após plotar

    st.markdown("---")

    # Bloco 2: Linhas Movimentadas e Serviços
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

    # Bloco 3: Tipo de Tarifa e Detalhe de Rotas
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
