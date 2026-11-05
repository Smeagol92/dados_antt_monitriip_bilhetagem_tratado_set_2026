        "tipo_tarifa",
        "Bilhetes por tipo de tarifa",
    )

with col2:
    grafico_rosca(
        dfs_dim["nacionalidade"],
        "nacional_internacional",
        "Bilhetes por nacionalidade",
    )

col3, col4 = st.columns(2)

with col3:
    grafico_rosca(
        dfs_dim["ambito"],
        "estadual_interestadual",
        "Bilhetes por âmbito da viagem",
    )

with col4:
    grafico_rosca(
        dfs_dim["antecedencia"],
        "meses_antecedencia",
        "Bilhetes por meses de antecedência",
    )

col5, col6 = st.columns(2)

with col5:
    grafico_barras(
        dfs_dim["origem_uf"],
        "ponto_origem_viagem_uf",
        "Principais UFs de origem",
        top_n=10,
    )

with col6:
    grafico_barras(
        dfs_dim["destino_uf"],
        "ponto_destino_viagem_uf",
        "Principais UFs de destino",
        top_n=10,
    )

col7, col8 = st.columns(2)

with col7:
    grafico_barras(
        dfs_dim["servico"],
        "tipo_servico",
        "Bilhetes por tipo de serviço",
        top_n=15,
    )

with col8:
    grafico_barras(
        dfs_dim["gratuidade"],
        "tipo_gratuidade",
        "Bilhetes por tipo de gratuidade",
        top_n=15,
    )

# ============================================================
# ROTAS — EXIBIDAS SOMENTE SE A BASE EXISTIR
# ============================================================
if not dfs_dim["rota_unica"].empty:
    st.divider()
    st.subheader("🚌 Principais rotas")
    grafico_barras(
        dfs_dim["rota_unica"],
        "rota_unica",
        "Top 10 rotas por quantidade de bilhetes",
        top_n=10,
    )

# ============================================================
# TABELA DE DADOS E NOTAS METODOLÓGICAS
# ============================================================
with st.expander("Consultar dados mensais utilizados nos KPIs"):
    tabela_kpis = df_geral[
        ["data_viagem", "total_bilhetes", "total_arrecadacao"]
    ].copy()

    tabela_kpis["ticket_medio_calculado"] = (
        tabela_kpis["total_arrecadacao"]
        / tabela_kpis["total_bilhetes"].replace(0, pd.NA)
    )

    st.dataframe(
        tabela_kpis.sort_values("data_viagem"),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Notas metodológicas"):
    st.markdown(
        """
        - **Bilhetes emitidos:** soma de `total_bilhetes` da tabela geral.
        - **Arrecadação:** soma de `total_arrecadacao` da tabela geral.
        - **Ticket médio:** arrecadação total dividida pelo total de bilhetes.
        - **Antecedência zero:** participação dos bilhetes classificados com
          zero mês de antecedência sobre o total da tabela de antecedência.
        - **Filtros dimensionais:** atuam somente sobre o gráfico da dimensão
          correspondente; não alteram os KPIs gerais.
        - **Limitação:** as tabelas agregadas separadamente não permitem
          inferir cruzamentos entre dimensões (por exemplo, origem + destino
          + tarifa) no nível de cada bilhete.
        """
    )

st.caption(
    "Fonte: dados de bilhetagem do Monitriip/ANTT disponibilizados no "
    "repositório deste projeto. Consulte a documentação da base para "
    "interpretação das variáveis e do período de referência."
)
