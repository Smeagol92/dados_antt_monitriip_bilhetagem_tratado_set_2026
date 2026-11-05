import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Dashboard ANTT | Monitriip",
    page_icon="🚌",
    layout="wide",
)

st.title("🚌 Dashboard ANTT | Bilhetagem Monitriip")
st.caption("Indicadores históricos de bilhetagem e arrecadação.")

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "Smeagol92/dados_antt_monitriip_bilhetagem_tratado_set_2026/"
    "main/data/"
)

# A tabela de rotas está configurada como opcional porque o endereço
# tabela_rota_unica.csv atualmente retorna 404 no repositório.
FILES = {
    "geral": "tabela_data_viagem_geral.csv",
    "ambito": "tabela_estadual_interestadual.csv",
    "antecedencia": "tabela_meses_antecedencia.csv",
    "nacionalidade": "tabela_nacional_internacional.csv",
    "origem": "tabela_ponto_origem_viagem_uf.csv",
    "destino": "tabela_ponto_destino_viagem_uf.csv",
    "gratuidade": "tabela_tipo_gratuidade.csv",
    "servico": "tabela_tipo_servico.csv",
    "tarifa": "tabela_tipo_tarifa.csv",
    "rota": "tabela_rota_unica.csv",  # opcional
}

DIMENSIONS = {
    "ambito": ("estadual_interestadual", "Âmbito da viagem"),
    "antecedencia": ("meses_antecedencia", "Meses de antecedência"),
    "nacionalidade": ("nacional_internacional", "Nacionalidade"),
    "origem": ("ponto_origem_viagem_uf", "UF de origem"),
    "destino": ("ponto_destino_viagem_uf", "UF de destino"),
    "gratuidade": ("tipo_gratuidade", "Tipo de gratuidade"),
    "servico": ("tipo_servico", "Tipo de serviço"),
    "tarifa": ("tipo_tarifa", "Tipo de tarifa"),
    "rota": ("rota_unica", "Rota"),
}

REQUIRED = {
    "geral": ["data_viagem", "total_bilhetes", "total_arrecadacao"],
    "ambito": ["data_viagem", "estadual_interestadual", "total_bilhetes"],
    "antecedencia": ["data_viagem", "meses_antecedencia", "total_bilhetes"],
    "nacionalidade": ["data_viagem", "nacional_internacional", "total_bilhetes"],
    "origem": ["data_viagem", "ponto_origem_viagem_uf", "total_bilhetes"],
    "destino": ["data_viagem", "ponto_destino_viagem_uf", "total_bilhetes"],
    "gratuidade": ["data_viagem", "tipo_gratuidade", "total_bilhetes"],
    "servico": ["data_viagem", "tipo_servico", "total_bilhetes"],
    "tarifa": ["data_viagem", "tipo_tarifa", "total_bilhetes"],
    "rota": ["data_viagem", "rota_unica", "total_bilhetes"],
}


# ============================================================
# 2. CARREGAMENTO E VALIDAÇÃO
# ============================================================
@st.cache_data(ttl=3600, show_spinner="Carregando arquivos do GitHub...")
def load_data():
    data = {}
    warnings = []

    for key, filename in FILES.items():
        url = BASE_URL + filename

        try:
            df = pd.read_csv(
                url,
                sep=";",
                encoding="utf-8-sig",
                low_memory=False,
            )
        except Exception as exc:
            if key == "rota":
                data[key] = pd.DataFrame()
                warnings.append(
                    f"Gráfico de rotas indisponível: não foi possível carregar "
                    f"{filename}. Verifique se esse arquivo existe no GitHub."
                )
                continue

            raise RuntimeError(
                f"Erro ao carregar {filename}: {exc}"
            ) from exc

        df.columns = df.columns.str.strip()

        missing = [c for c in REQUIRED[key] if c not in df.columns]
        if missing:
            if key == "rota":
                data[key] = pd.DataFrame()
                warnings.append(
                    "Gráfico de rotas indisponível: a tabela não possui "
                    f"as colunas esperadas: {', '.join(missing)}."
                )
                continue
            raise ValueError(
                f"{filename}: coluna(s) obrigatória(s) ausente(s): "
                f"{', '.join(missing)}"
            )

        df["data_viagem_dt"] = pd.to_datetime(
            df["data_viagem"].astype(str).str.strip(),
            format="%Y-%m",
            errors="coerce",
        )
        df = df.dropna(subset=["data_viagem_dt"]).copy()

        for col in [
            "total_bilhetes",
            "total_arrecadacao",
            "ticket_medio",
            "proporcao_bilhetes",
            "proporcao_arrecadacao",
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["total_bilhetes"] = df["total_bilhetes"].fillna(0)
        if "total_arrecadacao" in df.columns:
            df["total_arrecadacao"] = df["total_arrecadacao"].fillna(0)

        dim_col = DIMENSIONS.get(key, (None, None))[0]
        if dim_col and dim_col in df.columns:
            if key == "antecedencia":
                df[dim_col] = pd.to_numeric(df[dim_col], errors="coerce")
            else:
                df[dim_col] = df[dim_col].astype("string").str.strip()

        data[key] = df

    return data, warnings


try:
    dfs, load_warnings = load_data()
except Exception as exc:
    st.error("Não foi possível iniciar o dashboard.")
    st.exception(exc)
    st.stop()

for message in load_warnings:
    st.warning(message)

if dfs["geral"].empty:
    st.error("A tabela geral não possui registros válidos.")
    st.stop()


# ============================================================
# 3. FUNÇÕES DE APOIO
# ============================================================
def filter_period(df, start_date, end_date):
    if df.empty:
        return df.copy()
    return df.loc[
        df["data_viagem_dt"].between(start_date, end_date)
    ].copy()


def apply_dimension_filter(df, column, selected):
    if df.empty or not selected:
        return df.copy()
    return df.loc[df[column].isin(selected)].copy()


def br_number(value):
    return f"{value:,.0f}".replace(",", ".")


def brl(value):
    return (
        f"R$ {value:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def show_pie(df, column, title):
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    summary = (
        df.groupby(column, dropna=False)["total_bilhetes"]
        .sum()
        .reset_index()
    )
    summary = summary[summary["total_bilhetes"] > 0]

    if summary.empty:
        st.info("Não há bilhetes para apresentar.")
        return

    fig = px.pie(
        summary,
        names=column,
        values="total_bilhetes",
        hole=0.38,
        title=title,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=390, margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(fig, use_container_width=True)


def show_top_bar(df, column, title, limit=10):
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    summary = (
        df.groupby(column, dropna=False)["total_bilhetes"]
        .sum()
        .nlargest(limit)
        .sort_values()
        .reset_index()
    )

    if summary.empty:
        st.info("Não há registros para apresentar.")
        return

    fig = px.bar(
        summary,
        x="total_bilhetes",
        y=column,
        orientation="h",
        title=title,
        text="total_bilhetes",
    )
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(
        height=max(350, 34 * len(summary)),
        xaxis_title="Quantidade de bilhetes",
        yaxis_title="",
        margin=dict(l=10, r=35, t=55, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 4. FILTRO DE PERÍODO E MENU LATERAL
# ============================================================
st.sidebar.header("Filtros do dashboard")

available_dates = sorted(dfs["geral"]["data_viagem_dt"].dropna().unique())
if not available_dates:
    st.error("Não foram encontradas datas válidas na tabela geral.")
    st.stop()

start_date, end_date = st.sidebar.select_slider(
    "Período da viagem (MM/YYYY)",
    options=available_dates,
    value=(available_dates[0], available_dates[-1]),
    format_func=lambda x: pd.Timestamp(x).strftime("%m/%Y"),
)

# Aplica o período a todas as tabelas.
period_data = {
    key: filter_period(df, start_date, end_date)
    for key, df in dfs.items()
}

st.sidebar.divider()
st.sidebar.subheader("Filtros por dimensão")
st.sidebar.caption(
    "Cada seleção filtra o gráfico da dimensão correspondente. "
    "As tabelas fornecidas são agregadas separadamente e não permitem "
    "cruzar todas as dimensões no nível do bilhete."
)

selected = {}
for key, (column, label) in DIMENSIONS.items():
    df = period_data.get(key, pd.DataFrame())

    if df.empty or column not in df.columns:
        selected[key] = []
        continue

    options = df[column].dropna().unique().tolist()
    try:
        options = sorted(options)
    except TypeError:
        options = sorted(options, key=str)

    selected[key] = st.sidebar.multiselect(
        label,
        options=options,
        key=f"filter_{key}",
        disabled=(key == "rota" and df.empty),
    )

# Cada filtro dimensional atua apenas na sua tabela.
dimension_data = {}
for key, (column, _) in DIMENSIONS.items():
    df = period_data.get(key, pd.DataFrame())
    if not df.empty and column in df.columns:
        dimension_data[key] = apply_dimension_filter(
            df, column, selected.get(key, [])
        )
    else:
        dimension_data[key] = df.copy()


# ============================================================
# 5. KPIs
# ============================================================
# Os KPIs gerais são calculados pela tabela geral e pelo período.
# Não se aplica interseção artificial de meses com filtros dimensionais.
general_period = period_data["geral"]

total_tickets = general_period["total_bilhetes"].sum()
total_revenue = general_period["total_arrecadacao"].sum()
average_ticket = total_revenue / total_tickets if total_tickets else 0

# O KPI de antecedência zero usa todas as categorias da tabela de
# antecedência no período, independentemente do multiselect da lateral.
antecedencia_period = period_data["antecedencia"]
if not antecedencia_period.empty:
    total_antecedencia = antecedencia_period["total_bilhetes"].sum()
    tickets_zero = antecedencia_period.loc[
        antecedencia_period["meses_antecedencia"] == 0,
        "total_bilhetes",
    ].sum()
    pct_zero = (
        tickets_zero / total_antecedencia * 100
        if total_antecedencia
        else 0
    )
else:
    pct_zero = 0

st.subheader("Indicadores do período")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de bilhetes", br_number(total_tickets))
k2.metric("Faturamento total", brl(total_revenue))
k3.metric("Ticket médio", brl(average_ticket))
k4.metric("Antecedência zero", f"{pct_zero:.2f}%")

st.caption(
    "A categoria '0 mês' representa antecedência classificada como zero "
    "na base; não deve ser interpretada automaticamente como compra "
    "realizada no mesmo dia."
)


# ============================================================
# 6. EVOLUÇÃO TEMPORAL — TABELA GERAL
# ============================================================
st.divider()
st.subheader("📈 Evolução temporal: bilhetes x faturamento")

if general_period.empty:
    st.info("Não há dados gerais no período selecionado.")
else:
    temporal = (
        general_period.groupby("data_viagem_dt", as_index=False)
        .agg(
            total_bilhetes=("total_bilhetes", "sum"),
            total_arrecadacao=("total_arrecadacao", "sum"),
        )
        .sort_values("data_viagem_dt")
    )

    fig_time = make_subplots(specs=[[{"secondary_y": True}]])
    fig_time.add_trace(
        go.Bar(
            x=temporal["data_viagem_dt"],
            y=temporal["total_bilhetes"],
            name="Bilhetes",
            marker_color="#1D3557",
        ),
        secondary_y=False,
    )
    fig_time.add_trace(
        go.Scatter(
            x=temporal["data_viagem_dt"],
            y=temporal["total_arrecadacao"],
            name="Faturamento",
            mode="lines+markers",
            line=dict(color="#E76F51", width=3),
        ),
        secondary_y=True,
    )
    fig_time.update_layout(
        height=440,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12, x=0),
    )
    fig_time.update_yaxes(title_text="Bilhetes", secondary_y=False)
    fig_time.update_yaxes(title_text="Faturamento (R$)", secondary_y=True)
    fig_time.update_xaxes(title_text="Mês da viagem")
    st.plotly_chart(fig_time, use_container_width=True)


# ============================================================
# 7. TOP 10 ROTAS
# ============================================================
st.divider()
st.subheader("🚌 Top 10 rotas mais movimentadas")

if dimension_data["rota"].empty:
    st.warning(
        "O gráfico de rotas depende de tabela_rota_unica.csv. "
        "Esse arquivo não está disponível no caminho atualmente configurado "
        "no GitHub. Inclua a tabela na pasta data ou ajuste o nome do arquivo "
        "em FILES['rota']."
    )
else:
    show_top_bar(
        dimension_data["rota"],
        "rota_unica",
        "Top 10 rotas por quantidade de bilhetes",
        limit=10,
    )


# ============================================================
# 8. PARTICIPAÇÃO POR TARIFA E NACIONALIDADE
# ============================================================
st.divider()
left, right = st.columns(2)

with left:
    show_pie(
        dimension_data["tarifa"],
        "tipo_tarifa",
        "Participação por tipo de tarifa",
    )

with right:
    show_pie(
        dimension_data["nacionalidade"],
        "nacional_internacional",
        "Participação por nacionalidade",
    )


# ============================================================
# 9. PARTICIPAÇÃO POR ESTADO DE DESTINO
# ============================================================
st.divider()
show_top_bar(
    dimension_data["destino"],
    "ponto_destino_viagem_uf",
    "Estados de destino com maior volume de bilhetes",
    limit=27,
)


# ============================================================
# 10. GRÁFICOS ADICIONAIS PARA OS FILTROS DO MENU
# ============================================================
st.divider()
st.subheader("Análises complementares")

c1, c2 = st.columns(2)
with c1:
    show_pie(
        dimension_data["ambito"],
        "estadual_interestadual",
        "Participação por âmbito da viagem",
    )
with c2:
    show_pie(
        dimension_data["antecedencia"],
        "meses_antecedencia",
        "Distribuição por meses de antecedência",
    )

c3, c4 = st.columns(2)
with c3:
    show_top_bar(
        dimension_data["origem"],
        "ponto_origem_viagem_uf",
        "Principais UFs de origem",
        limit=10,
    )
with c4:
    show_pie(
        dimension_data["gratuidade"],
        "tipo_gratuidade",
        "Participação por tipo de gratuidade",
    )

show_pie(
    dimension_data["servico"],
    "tipo_servico",
    "Participação por tipo de serviço",
)


# ============================================================
# 11. NOTAS METODOLÓGICAS E FONTE
# ============================================================
with st.expander("Notas metodológicas"):
    st.markdown(
        """
        - Os KPIs gerais e a série temporal são calculados a partir da
          tabela `tabela_data_viagem_geral.csv`.
        - O ticket médio exibido é calculado como faturamento total dividido
          pelo total de bilhetes.
        - O percentual de antecedência zero é calculado sobre o total de
          bilhetes da tabela de antecedência no período selecionado.
        - Os filtros de dimensão atuam somente sobre o gráfico da dimensão
          correspondente.
        - As tabelas agregadas separadamente não permitem cruzar, por
          exemplo, UF de origem + UF de destino + tipo de tarifa como se
          fossem registros individuais de bilhetes.
        - O gráfico de rotas depende da existência da tabela de rotas e das
          colunas `data_viagem`, `rota_unica` e `total_bilhetes`.
        """
    )

st.caption(
    "Fonte: dados de bilhetagem Monitriip/ANTT disponibilizados no "
    "repositório do projeto."
)
