import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Dashboard ANTT | Monitriip",
    page_icon="🚌",
    layout="wide",
)

# Cards (st.metric) com fonte um pouco menor que o padrão do Streamlit.
st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 1.7rem; }
    [data-testid="stMetricLabel"] p { font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚌 Dashboard ANTT | Bilhetagem Monitriip")
st.caption("Indicadores históricos de bilhetagem e arrecadação.")

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "Smeagol92/dados_antt_monitriip_bilhetagem_tratado_set_2026/"
    "main/data/"
)

# A tabela de rotas é tratada como opcional: se o arquivo não puder ser
# carregado, apenas os gráficos de rota ficam indisponíveis.
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
    "geral": ["data_emissao_bilhete", "total_bilhetes", "total_arrecadacao"],
    "ambito": ["data_emissao_bilhete", "estadual_interestadual", "total_bilhetes"],
    "antecedencia": ["data_emissao_bilhete", "meses_antecedencia", "total_bilhetes"],
    "nacionalidade": ["data_emissao_bilhete", "nacional_internacional", "total_bilhetes"],
    "origem": ["data_emissao_bilhete", "ponto_origem_viagem_uf", "total_bilhetes"],
    "destino": ["data_emissao_bilhete", "ponto_destino_viagem_uf", "total_bilhetes"],
    "gratuidade": ["data_emissao_bilhete", "tipo_gratuidade", "total_bilhetes"],
    "servico": ["data_emissao_bilhete", "tipo_servico", "total_bilhetes"],
    "tarifa": ["data_emissao_bilhete", "tipo_tarifa", "total_bilhetes"],
    "rota": ["data_emissao_bilhete", "rota_unica", "total_bilhetes"],
}

# Métricas exibidas nos gráficos e a cor fixa de cada uma.
COLOR_TICKETS = "#1D3557"
COLOR_REVENUE = "#E76F51"

METRICS = {
    "tickets": {
        "col": "total_bilhetes",
        "label": "Bilhetes",
        "axis": "Quantidade de bilhetes",
        "color": COLOR_TICKETS,
    },
    "revenue": {
        "col": "total_arrecadacao",
        "label": "Faturamento",
        "axis": "Faturamento (R$)",
        "color": COLOR_REVENUE,
    },
}

# Paleta categórica (ordem fixa, máximo de 8 séries) para as linhas
# da evolução temporal por dimensão.
SERIES_COLORS = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#e34948",
]


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

        df["data_emissao_bilhete_dt"] = pd.to_datetime(
            df["data_emissao_bilhete"].astype(str).str.strip(),
            format="%Y-%m",
            errors="coerce",
        )
        df = df.dropna(subset=["data_emissao_bilhete_dt"]).copy()

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
        df["data_emissao_bilhete_dt"].between(start_date, end_date)
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


def compact_number(value):
    """Formata números grandes de forma curta: 899 mil, 1,2 mi, 3,45 bi."""
    absolute = abs(value)
    if absolute >= 1e9:
        text = f"{value / 1e9:.2f} bi"
    elif absolute >= 1e6:
        text = f"{value / 1e6:.1f} mi"
    elif absolute >= 1e3:
        text = f"{value / 1e3:.0f} mil"
    else:
        text = f"{value:.0f}"
    return text.replace(".", ",")


def share_text(pct):
    if pct < 0.1:
        return "<0,1%"
    return f"{pct:.1f}%".replace(".", ",")


def wrap_label(text, width):
    return "<br>".join(textwrap.wrap(str(text), width=width)) or str(text)


def show_bar(
    df,
    column,
    metric_key,
    title,
    orientation="h",
    limit=None,
    show_share=True,
    numeric_order=False,
    axis_label="",
    wrap=55,
):
    """Gráfico de barras (horizontal 'h' ou vertical 'v') somando a métrica
    por categoria. Substitui os antigos gráficos de pizza/rosca e também
    serve para os rankings e para os gráficos de faturamento."""
    metric = METRICS[metric_key]
    value_col = metric["col"]

    if df.empty or column not in df.columns or value_col not in df.columns:
        st.info("Sem dados para os filtros selecionados.")
        return

    summary = df.groupby(column)[value_col].sum().reset_index()
    summary = summary[summary[value_col] > 0]

    if summary.empty:
        st.info("Não há registros para apresentar.")
        return

    # A participação é calculada sobre o total de todas as categorias,
    # antes de aplicar o limite do ranking.
    summary["share"] = summary[value_col] / summary[value_col].sum() * 100

    if limit:
        summary = summary.nlargest(limit, value_col)

    if numeric_order:
        summary = summary.sort_values(column)
        summary["label"] = summary[column].map(lambda v: str(int(v)))
    else:
        summary = summary.sort_values(value_col, ascending=False)
        summary["label"] = summary[column].astype(str)

    if orientation == "h":
        summary["axis_label"] = summary["label"].map(
            lambda t: wrap_label(t, wrap)
        )
    else:
        summary["axis_label"] = summary["label"]

    def value_text(v):
        if metric_key == "revenue" and orientation == "h":
            return "R$ " + compact_number(v)
        return compact_number(v)

    summary["text"] = summary[value_col].map(value_text)
    if show_share:
        summary["text"] = summary["text"] + " (" + summary["share"].map(
            share_text
        ) + ")"

    axis_ref = "x" if orientation == "h" else "y"
    if metric_key == "tickets":
        value_hover = f"Bilhetes: %{{{axis_ref}:,.0f}}"
    else:
        value_hover = f"Faturamento: R$ %{{{axis_ref}:,.2f}}"
    hover = (
        "<b>%{customdata[0]}</b><br>"
        + value_hover
        + "<br>Participação: %{customdata[1]:.1f}%<extra></extra>"
    )

    values = summary[value_col]
    if orientation == "h":
        x, y = values, summary["axis_label"]
    else:
        x, y = summary["axis_label"], values

    fig = go.Figure(
        go.Bar(
            x=x,
            y=y,
            orientation=orientation,
            marker_color=metric["color"],
            text=summary["text"],
            textposition="outside",
            cliponaxis=False,
            customdata=list(zip(summary["label"], summary["share"])),
            hovertemplate=hover,
        )
    )

    peak = float(values.max())
    n = len(summary)

    if orientation == "h":
        lines = int(summary["axis_label"].str.count("<br>").max()) + 1
        height = max(320, (18 + 14 * lines) * n + 90)
        pad = 1.45 if show_share else 1.25
        fig.update_yaxes(
            type="category",
            autorange="reversed",
            automargin=True,
            title_text="",
        )
        fig.update_xaxes(range=[0, peak * pad], title_text=metric["axis"])
    else:
        height = 430
        pad = 1.2 if show_share else 1.15
        fig.update_xaxes(
            type="category",
            automargin=True,
            title_text=axis_label,
        )
        fig.update_yaxes(range=[0, peak * pad], title_text=metric["axis"])

    fig.update_layout(
        title=title,
        height=height,
        separators=",.",
        margin=dict(l=10, r=40, t=55, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def show_pair(df, column, title, side_by_side=True, **kwargs):
    """Mostra o gráfico de bilhetes e o de faturamento da mesma dimensão,
    lado a lado ou um abaixo do outro (largura total)."""
    if df.empty:
        st.info("Sem dados para os filtros selecionados.")
        return

    if side_by_side:
        left, right = st.columns(2)
        with left:
            show_bar(df, column, "tickets", f"{title} — bilhetes", **kwargs)
        with right:
            show_bar(df, column, "revenue", f"{title} — faturamento", **kwargs)
    else:
        show_bar(df, column, "tickets", f"{title} — bilhetes", **kwargs)
        show_bar(df, column, "revenue", f"{title} — faturamento", **kwargs)


def show_temporal_lines(
    df, column, dim_label, metric_key, top_n, months, numeric_order=False
):
    """Linhas mensais, uma por categoria da dimensão escolhida."""
    metric = METRICS[metric_key]
    value_col = metric["col"]

    if df.empty or column not in df.columns or value_col not in df.columns:
        st.info("Sem dados para os filtros selecionados.")
        return

    totals = df.groupby(column)[value_col].sum()
    totals = totals[totals > 0].sort_values(ascending=False)

    if totals.empty:
        st.info("Não há registros para apresentar.")
        return

    top = totals.head(top_n).index.tolist()

    # Meses sem registro da categoria contam como zero.
    monthly = (
        df[df[column].isin(top)]
        .pivot_table(
            index="data_emissao_bilhete_dt",
            columns=column,
            values=value_col,
            aggfunc="sum",
        )
        .reindex(index=months, columns=top)
        .fillna(0)
    )

    fig = go.Figure()
    for i, category in enumerate(top):
        full_name = str(int(category)) if numeric_order else str(category)
        legend_name = (
            full_name if len(full_name) <= 60 else full_name[:59] + "…"
        )
        if metric_key == "tickets":
            hover = f"{full_name}: %{{y:,.0f}}<extra></extra>"
        else:
            hover = f"{full_name}: R$ %{{y:,.2f}}<extra></extra>"

        fig.add_trace(
            go.Scatter(
                x=monthly.index,
                y=monthly[category],
                name=legend_name,
                mode="lines",
                line=dict(color=SERIES_COLORS[i], width=2.5),
                hovertemplate=hover,
            )
        )

    fig.update_layout(
        height=470,
        hovermode="x unified",
        separators=",.",
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(
        title_text="Mês da viagem", tickformat="%m/%Y", hoverformat="%m/%Y"
    )
    fig.update_yaxes(title_text=metric["axis"])
    st.plotly_chart(fig, use_container_width=True)

    if len(totals) > top_n:
        st.caption(
            f"Exibindo as {top_n} maiores categorias de {dim_label} no "
            f"período, por {metric['label'].lower()} (de {len(totals)} no "
            "total). Ajuste a quantidade de séries acima."
        )


# ============================================================
# 4. FILTRO DE PERÍODO E MENU LATERAL
# ============================================================
st.sidebar.header("Filtros do dashboard")

available_dates = sorted(dfs["geral"]["data_emissao_bilhete_dt"].dropna().unique())
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
# 6. EVOLUÇÃO TEMPORAL
# ============================================================
st.divider()
st.subheader("📈 Evolução temporal")

GENERAL_LABEL = "Geral (bilhetes x faturamento)"
temporal_options = {GENERAL_LABEL: None}
for dim_key, (_, dim_label) in DIMENSIONS.items():
    temporal_options[dim_label] = dim_key

t1, t2, t3 = st.columns([2, 1, 1])
with t1:
    temporal_choice = st.selectbox(
        "Visualizar evolução por",
        options=list(temporal_options.keys()),
    )
temporal_key = temporal_options[temporal_choice]

if temporal_key is None:
    # Visão geral: bilhetes (barras) x faturamento (linha).
    if general_period.empty:
        st.info("Não há dados gerais no período selecionado.")
    else:
        temporal = (
            general_period.groupby("data_emissao_bilhete_dt", as_index=False)
            .agg(
                total_bilhetes=("total_bilhetes", "sum"),
                total_arrecadacao=("total_arrecadacao", "sum"),
            )
            .sort_values("data_emissao_bilhete_dt")
        )

        fig_time = make_subplots(specs=[[{"secondary_y": True}]])
        fig_time.add_trace(
            go.Bar(
                x=temporal["data_emissao_bilhete_dt"],
                y=temporal["total_bilhetes"],
                name="Bilhetes",
                marker_color=COLOR_TICKETS,
            ),
            secondary_y=False,
        )
        fig_time.add_trace(
            go.Scatter(
                x=temporal["data_emissao_bilhete_dt"],
                y=temporal["total_arrecadacao"],
                name="Faturamento",
                mode="lines+markers",
                line=dict(color=COLOR_REVENUE, width=3),
            ),
            secondary_y=True,
        )
        fig_time.update_layout(
            height=440,
            hovermode="x unified",
            separators=",.",
            legend=dict(orientation="h", y=1.12, x=0),
        )
        fig_time.update_yaxes(title_text="Bilhetes", secondary_y=False)
        fig_time.update_yaxes(title_text="Faturamento (R$)", secondary_y=True)
        fig_time.update_xaxes(title_text="Mês da viagem")
        st.plotly_chart(fig_time, use_container_width=True)
else:
    with t2:
        metric_choice = st.radio(
            "Métrica",
            options=["Bilhetes", "Faturamento"],
            horizontal=True,
        )
    with t3:
        top_n = st.slider("Séries exibidas (maiores)", 2, 8, 5)

    temporal_metric = "tickets" if metric_choice == "Bilhetes" else "revenue"
    temporal_column, temporal_label = DIMENSIONS[temporal_key]
    months = pd.DatetimeIndex(
        sorted(general_period["data_emissao_bilhete_dt"].unique())
    )

    show_temporal_lines(
        dimension_data[temporal_key],
        temporal_column,
        temporal_label,
        temporal_metric,
        top_n,
        months,
        numeric_order=(temporal_key == "antecedencia"),
    )


# ============================================================
# 7. TOP 20 ROTAS
# ============================================================
st.divider()
st.subheader("🚌 Top 20 rotas mais movimentadas")

if dimension_data["rota"].empty:
    st.warning(
        "O gráfico de rotas depende de tabela_rota_unica.csv. "
        "Esse arquivo não está disponível no caminho atualmente configurado "
        "no GitHub. Inclua a tabela na pasta data ou ajuste o nome do arquivo "
        "em FILES['rota']."
    )
else:
    show_bar(
        dimension_data["rota"],
        "rota_unica",
        "tickets",
        "Top 20 rotas por quantidade de bilhetes",
        limit=20,
        show_share=False,
    )
    show_bar(
        dimension_data["rota"],
        "rota_unica",
        "revenue",
        "Top 20 rotas por faturamento",
        limit=20,
        show_share=False,
    )


# ============================================================
# 8. PARTICIPAÇÃO POR TARIFA E NACIONALIDADE
# ============================================================
st.divider()
st.subheader("Participação por tipo de tarifa")
show_pair(
    dimension_data["tarifa"],
    "tipo_tarifa",
    "Participação por tipo de tarifa",
)

st.divider()
st.subheader("Participação por nacionalidade")
show_pair(
    dimension_data["nacionalidade"],
    "nacional_internacional",
    "Participação por nacionalidade",
)


# ============================================================
# 9. ESTADO DE DESTINO (GRÁFICOS NA VERTICAL)
# ============================================================
st.divider()
st.subheader("Estados de destino com maior volume de bilhetes")
show_pair(
    dimension_data["destino"],
    "ponto_destino_viagem_uf",
    "Estados de destino",
    side_by_side=False,
    orientation="v",
    limit=27,
    show_share=False,
    axis_label="UF de destino",
)


# ============================================================
# 10. ANÁLISES COMPLEMENTARES
# ============================================================
st.divider()
st.subheader("Análises complementares")

st.markdown("#### Âmbito da viagem")
show_pair(
    dimension_data["ambito"],
    "estadual_interestadual",
    "Participação por âmbito da viagem",
)

st.markdown("#### Meses de antecedência")
show_pair(
    dimension_data["antecedencia"],
    "meses_antecedencia",
    "Distribuição por meses de antecedência",
    orientation="v",
    numeric_order=True,
    show_share=False,
    axis_label="Meses de antecedência",
)

st.markdown("#### UF de origem")
show_pair(
    dimension_data["origem"],
    "ponto_origem_viagem_uf",
    "Principais UFs de origem",
    limit=10,
    show_share=False,
)

st.markdown("#### Tipo de gratuidade")
show_pair(
    dimension_data["gratuidade"],
    "tipo_gratuidade",
    "Participação por tipo de gratuidade",
    side_by_side=False,
)

st.markdown("#### Tipo de serviço")
show_pair(
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
        - Os KPIs gerais e a visão geral da série temporal são calculados a
          partir da tabela `tabela_data_viagem_geral.csv`.
        - A evolução temporal por dimensão usa a tabela da dimensão escolhida
          e mostra as maiores categorias do período (até 8 linhas). Meses sem
          registro de uma categoria são tratados como zero.
        - O ticket médio exibido é calculado como faturamento total dividido
          pelo total de bilhetes.
        - O percentual de antecedência zero é calculado sobre o total de
          bilhetes da tabela de antecedência no período selecionado.
        - Nos gráficos de participação, o percentual é calculado sobre o total
          de todas as categorias da dimensão no período, mesmo quando só as
          maiores são exibidas. Os rankings de bilhetes e de faturamento são
          calculados de forma independente.
        - Os filtros de dimensão atuam somente sobre o gráfico da dimensão
          correspondente.
        - As tabelas agregadas separadamente não permitem cruzar, por
          exemplo, UF de origem + UF de destino + tipo de tarifa como se
          fossem registros individuais de bilhetes.
        - O gráfico de rotas depende da existência da tabela de rotas e das
          colunas `data_emissao_bilhete`, `rota_unica` e `total_bilhetes`.
        """
    )

st.caption(
    "Fonte: dados de bilhetagem Monitriip/ANTT disponibilizados no "
    "repositório do projeto."
)
