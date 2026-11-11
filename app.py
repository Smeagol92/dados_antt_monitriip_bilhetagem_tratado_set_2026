import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import ml  # funções de machine learning (arquivo ml.py na mesma pasta)

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
    "Cada seleção filtra o gráfico da dimensão correspondente e os cards "
    "de indicadores. As tabelas fornecidas são agregadas separadamente e "
    "não permitem cruzar todas as dimensões no nível do bilhete."
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

period_tickets = general_period["total_bilhetes"].sum()
period_revenue = general_period["total_arrecadacao"].sum()

# Dimensões com algum valor selecionado no menu lateral.
active_filters = [
    key
    for key in DIMENSIONS
    if selected.get(key) and not dimension_data[key].empty
]
# Um filtro que não retorna nenhuma linha também zera os cards.
empty_filters = [
    key
    for key in DIMENSIONS
    if selected.get(key) and dimension_data[key].empty
]

if empty_filters:
    total_tickets = 0
    total_revenue = 0
elif not active_filters:
    total_tickets = period_tickets
    total_revenue = period_revenue
else:
    # Cada tabela é agregada separadamente. Com um único filtro ativo, o
    # resultado é exato (soma das categorias selecionadas). Com vários
    # filtros, estima-se a interseção multiplicando a participação de
    # cada seleção sobre o total do período (hipótese de independência).
    total_tickets = period_tickets
    total_revenue = period_revenue
    if len(active_filters) == 1:
        sel_df = dimension_data[active_filters[0]]
        total_tickets = sel_df["total_bilhetes"].sum()
        total_revenue = sel_df["total_arrecadacao"].sum()
    else:
        share_tickets = 1.0
        share_revenue = 1.0
        for key in active_filters:
            sel_df = dimension_data[key]
            if period_tickets:
                share_tickets *= sel_df["total_bilhetes"].sum() / period_tickets
            if period_revenue:
                share_revenue *= sel_df["total_arrecadacao"].sum() / period_revenue
        total_tickets = period_tickets * share_tickets
        total_revenue = period_revenue * share_revenue

average_ticket = total_revenue / total_tickets if total_tickets else 0

# Antecedência zero: percentual de bilhetes com 0 mês de antecedência.
# Só muda quando o filtro de antecedência é usado; os demais filtros não
# podem ser cruzados com a antecedência nas tabelas disponíveis.
antecedencia_period = period_data["antecedencia"]
if selected.get("antecedencia"):
    antecedencia_base = dimension_data["antecedencia"]
else:
    antecedencia_base = antecedencia_period

if not antecedencia_base.empty:
    total_antecedencia = antecedencia_base["total_bilhetes"].sum()
    tickets_zero = antecedencia_base.loc[
        antecedencia_base["meses_antecedencia"] == 0,
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

if len(active_filters) > 1:
    st.warning(
        "Há filtros em mais de uma dimensão. Como as tabelas são agregadas "
        "separadamente, bilhetes e faturamento são uma estimativa (produto "
        "das participações de cada seleção, assumindo independência entre "
        "as dimensões). Com um único filtro, os valores são exatos."
    )
elif active_filters:
    st.caption(
        "Cards filtrados por: "
        + ", ".join(DIMENSIONS[k][1] for k in active_filters)
        + "."
    )

if "rota" in active_filters:
    st.caption(
        "A tabela de rotas cobre apenas as rotas mais movimentadas de cada "
        "mês; os valores refletem as rotas selecionadas."
    )

if any(k != "antecedencia" for k in active_filters) and not selected.get(
    "antecedencia"
):
    st.caption(
        "O percentual de antecedência zero só muda com o filtro de meses "
        "de antecedência, pois não há tabela que cruze essa dimensão com "
        "as demais."
    )

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
# 11. MACHINE LEARNING
# ============================================================
MONTH_NAMES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]
COLOR_OBSERVED = SERIES_COLORS[0]
COLOR_FORECAST = SERIES_COLORS[1]
COLOR_ALERT = SERIES_COLORS[7]
COLOR_MUTED = "#8a8a8a"

ML_METRICS = {
    "Bilhetes": ("tickets", "Quantidade de bilhetes"),
    "Faturamento": ("revenue", "Faturamento (R$)"),
    "Ticket médio": ("avg", "Ticket médio (R$)"),
}


def ml_format(metric_key, value):
    if pd.isna(value):
        return "—"
    if metric_key == "tickets":
        return br_number(value)
    return brl(value)


def ml_hover(metric_key):
    if metric_key == "tickets":
        return "%{y:,.0f}"
    if metric_key == "revenue":
        return "R$ %{y:,.0f}"
    return "R$ %{y:,.2f}"


def pct_text(value, signed=False):
    text = f"{value:+.1f}%" if signed else f"{value:.1f}%"
    return text.replace(".", ",")


def build_ml_series(dim_key, category, metric_key, months):
    """Série mensal completa (histórico inteiro) da dimensão/categoria."""
    if dim_key is None:
        df = dfs["geral"]
    else:
        df = dfs[dim_key]
        df = df[df[DIMENSIONS[dim_key][0]] == category]

    tickets = ml.monthly_series(df, "total_bilhetes", months)
    revenue = ml.monthly_series(df, "total_arrecadacao", months)

    if metric_key == "tickets":
        return tickets
    if metric_key == "revenue":
        return revenue
    return revenue / tickets.where(tickets > 0)


st.divider()
st.subheader("🤖 Machine learning")
st.caption(
    "Previsão, anomalias e decomposição usam todo o histórico da série "
    "escolhida (sem o filtro de período da lateral). O agrupamento de rotas "
    "respeita o período selecionado."
)

all_months = pd.date_range(
    dfs["geral"]["data_emissao_bilhete_dt"].min(),
    dfs["geral"]["data_emissao_bilhete_dt"].max(),
    freq="MS",
)

SERIES_DIMENSIONS = {"Geral (todas as viagens)": None}
for _key, (_col, _label) in DIMENSIONS.items():
    if _key != "rota":
        SERIES_DIMENSIONS[_label] = _key

with st.container(border=True):
    st.markdown("**Série analisada** (abas Previsão, Anomalias e Decomposição)")
    col_dim, col_cat, col_metric = st.columns([1.2, 1.6, 1.2])

    with col_dim:
        dim_choice = st.selectbox(
            "Dimensão", options=list(SERIES_DIMENSIONS), key="ml_dim"
        )
    ml_dim_key = SERIES_DIMENSIONS[dim_choice]
    ml_category = None

    with col_cat:
        if ml_dim_key is None:
            st.selectbox(
                "Categoria", options=["Todas"], disabled=True, key="ml_cat_all"
            )
        else:
            cat_col = DIMENSIONS[ml_dim_key][0]
            cat_df = dfs[ml_dim_key]
            if ml_dim_key == "antecedencia":
                categories = sorted(cat_df[cat_col].dropna().unique().tolist())
            else:
                categories = (
                    cat_df.groupby(cat_col)["total_bilhetes"]
                    .sum()
                    .sort_values(ascending=False)
                    .index.tolist()
                )
            ml_category = st.selectbox(
                "Categoria",
                options=categories,
                key=f"ml_cat_{ml_dim_key}",
                format_func=lambda v: (
                    str(int(v)) if ml_dim_key == "antecedencia" else str(v)
                ),
            )

    with col_metric:
        ml_metric_choice = st.selectbox(
            "Métrica da série", options=list(ML_METRICS), key="ml_metric"
        )
    ml_metric_key, ml_metric_axis = ML_METRICS[ml_metric_choice]

    tickets_general = ml.monthly_series(
        dfs["geral"], "total_bilhetes", all_months
    )
    suggested_exclude = ml.suggest_exclude_last(tickets_general)

    col_a, col_b = st.columns(2)
    with col_a:
        exclude_last = int(
            st.number_input(
                "Ignorar os últimos N meses no treino",
                min_value=0,
                max_value=12,
                value=suggested_exclude,
                step=1,
                help=(
                    "Meses recentes costumam estar com carga incompleta e "
                    "distorcem o treino. O valor inicial é sugerido "
                    "automaticamente pela base."
                ),
            )
        )
    with col_b:
        ignore_pandemic = st.checkbox(
            "Ignorar a pandemia (03/2020 a 12/2021) no treino",
            value=True,
        )

if suggested_exclude > 0:
    first_low = all_months[-suggested_exclude].strftime("%m/%Y")
    last_low = all_months[-1].strftime("%m/%Y")
    st.warning(
        f"Atenção à qualidade dos dados: de {first_low} a {last_low} a base "
        "tem menos de 50% do volume do mesmo mês do ano anterior, o que "
        "indica carga incompleta. Por padrão esses meses ficam fora do treino."
    )

category_text = (
    "Geral"
    if ml_dim_key is None
    else f"{dim_choice}: "
    + (str(int(ml_category)) if ml_dim_key == "antecedencia" else str(ml_category))
)
ml_title = f"{ml_metric_choice} — {category_text}"

ml_series = build_ml_series(ml_dim_key, ml_category, ml_metric_key, all_months)
use_mask = ml.training_mask(all_months, exclude_last, ignore_pandemic)

try:
    decomp, decomp_multiplicative = ml.decompose(ml_series, use_mask)
    decomp_error = None
except ValueError as exc:
    decomp, decomp_multiplicative, decomp_error = None, True, str(exc)

tab_forecast, tab_anomaly, tab_decomp, tab_cluster = st.tabs(
    [
        "📈 Previsão",
        "🚨 Anomalias",
        "🧩 Decomposição sazonal",
        "🗺️ Agrupamento de rotas",
    ]
)

# ---------------- Previsão ----------------
with tab_forecast:
    horizon = st.slider("Meses a prever", 3, 12, 12)
    try:
        fc_result = ml.forecast_series(ml_series, use_mask, horizon)
    except ValueError as exc:
        st.info(str(exc))
    else:
        fc = fc_result["forecast"]
        backtest = fc_result["backtest"]
        best_mape = float(backtest.loc[0, "MAPE (%)"])
        hover = ml_hover(ml_metric_key)

        fig_fc = go.Figure()
        fig_fc.add_trace(
            go.Scatter(
                x=ml_series.index,
                y=ml_series.where(use_mask),
                name="Histórico (treino)",
                mode="lines",
                line=dict(color=COLOR_OBSERVED, width=2.5),
                hovertemplate=f"Histórico: {hover}<extra></extra>",
            )
        )
        excluded_values = ml_series.where(~use_mask)
        if excluded_values.notna().any():
            fig_fc.add_trace(
                go.Scatter(
                    x=excluded_values.index,
                    y=excluded_values,
                    name="Meses fora do treino",
                    mode="markers",
                    marker=dict(color=COLOR_MUTED, size=7, symbol="x"),
                    hovertemplate=f"Fora do treino: {hover}<extra></extra>",
                )
            )
        fig_fc.add_trace(
            go.Scatter(
                x=fc.index,
                y=fc["upper"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig_fc.add_trace(
            go.Scatter(
                x=fc.index,
                y=fc["lower"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(235,104,52,0.18)",
                name="Faixa de 80%",
                hovertemplate=f"Mínimo (80%): {hover}<extra></extra>",
            )
        )
        fig_fc.add_trace(
            go.Scatter(
                x=fc.index,
                y=fc["pred"],
                name="Previsão",
                mode="lines+markers",
                line=dict(color=COLOR_FORECAST, width=2.5, dash="dash"),
                marker=dict(size=6),
                hovertemplate=f"Previsão: {hover}<extra></extra>",
            )
        )
        fig_fc.update_layout(
            title=f"Previsão — {ml_title}",
            height=450,
            hovermode="x unified",
            separators=",.",
            legend=dict(orientation="h", y=-0.15, x=0),
            margin=dict(l=10, r=10, t=55, b=10),
        )
        fig_fc.update_xaxes(tickformat="%m/%Y", hoverformat="%m/%Y")
        fig_fc.update_yaxes(title_text=ml_metric_axis)
        st.plotly_chart(fig_fc, use_container_width=True)

        f1, f2, f3 = st.columns(3)
        f1.metric("Erro do backtest (MAPE)", pct_text(best_mape))
        f2.metric("Meses usados no treino", str(fc_result["train_months"]))
        if ml_metric_key == "avg":
            f3.metric("Média prevista", brl(fc["pred"].mean()))
        else:
            f3.metric(
                f"Total previsto ({horizon} meses)",
                ml_format(ml_metric_key, fc["pred"].sum()),
            )

        st.markdown(f"**Modelo escolhido pelo backtest:** {fc_result['best']}")
        st.caption(
            f"A previsão começa em {fc.index[0].strftime('%m/%Y')}, logo "
            "após o último mês usado no treino. Os dois modelos foram "
            f"treinados sem os últimos {fc_result['holdout_months']} meses "
            "válidos e comparados nesse período (backtest); o de menor erro "
            "foi reajustado com todos os dados. A faixa de 80% usa o desvio "
            "dos erros do backtest e não cobre mudanças estruturais."
        )

        if best_mape > 50:
            st.warning(
                "O erro do backtest está muito alto. Provavelmente há meses "
                "incompletos ou atípicos no treino; ajuste os controles "
                "acima (últimos meses e pandemia)."
            )

        fc_view = pd.DataFrame(
            {
                "Mês": fc.index.strftime("%m/%Y"),
                "Previsão": [ml_format(ml_metric_key, v) for v in fc["pred"]],
                "Mínimo (80%)": [ml_format(ml_metric_key, v) for v in fc["lower"]],
                "Máximo (80%)": [ml_format(ml_metric_key, v) for v in fc["upper"]],
            }
        )
        with st.expander("Tabela da previsão e resultado do backtest"):
            st.dataframe(fc_view, hide_index=True, use_container_width=True)
            backtest_view = backtest.copy()
            backtest_view["MAPE (%)"] = backtest_view["MAPE (%)"].map(pct_text)
            st.dataframe(backtest_view, hide_index=True, use_container_width=True)

# ---------------- Anomalias ----------------
with tab_anomaly:
    if decomp_error:
        st.info(decomp_error)
    else:
        sensitivity = st.slider(
            "Sensibilidade (% de meses sinalizados)", 3, 15, 8
        )
        anomalies = ml.detect_anomalies(
            ml_series, decomp, decomp_multiplicative, sensitivity / 100
        )
        flagged = anomalies[anomalies["is_anomaly"]]
        hover = ml_hover(ml_metric_key)

        fig_an = go.Figure()
        fig_an.add_trace(
            go.Scatter(
                x=anomalies.index,
                y=anomalies["observed"],
                name="Observado",
                mode="lines",
                line=dict(color=COLOR_OBSERVED, width=2.5),
                hovertemplate=f"Observado: {hover}<extra></extra>",
            )
        )
        fig_an.add_trace(
            go.Scatter(
                x=anomalies.index,
                y=anomalies["expected"],
                name="Esperado (tendência × sazonalidade)",
                mode="lines",
                line=dict(color=COLOR_MUTED, width=2, dash="dash"),
                hovertemplate=f"Esperado: {hover}<extra></extra>",
            )
        )
        fig_an.add_trace(
            go.Scatter(
                x=flagged.index,
                y=flagged["observed"],
                name="Anomalia",
                mode="markers",
                marker=dict(
                    color=COLOR_ALERT,
                    size=11,
                    line=dict(width=2, color="white"),
                ),
                hovertemplate=f"Anomalia: {hover}<extra></extra>",
            )
        )
        fig_an.update_layout(
            title=f"Meses atípicos — {ml_title}",
            height=430,
            hovermode="x unified",
            separators=",.",
            legend=dict(orientation="h", y=-0.15, x=0),
            margin=dict(l=10, r=10, t=55, b=10),
        )
        fig_an.update_xaxes(tickformat="%m/%Y", hoverformat="%m/%Y")
        fig_an.update_yaxes(title_text=ml_metric_axis)
        st.plotly_chart(fig_an, use_container_width=True)

        st.caption(
            "Isolation Forest sobre três sinais de cada mês: desvio em "
            "relação ao esperado, variação sobre o mês anterior e variação "
            "sobre o mesmo mês do ano anterior. O modelo sempre sinaliza a "
            "fração escolhida de meses mais atípicos; os 12 primeiros meses "
            "não são avaliados."
        )

        if flagged.empty:
            st.info("Nenhum mês sinalizado.")
        else:
            ranked = flagged.sort_values("score", ascending=False)
            an_view = pd.DataFrame(
                {
                    "Mês": ranked.index.strftime("%m/%Y"),
                    "Observado": [
                        ml_format(ml_metric_key, v) for v in ranked["observed"]
                    ],
                    "Esperado": [
                        ml_format(ml_metric_key, v) for v in ranked["expected"]
                    ],
                    "Desvio": [
                        pct_text(d * 100, signed=True) for d in ranked["deviation"]
                    ],
                    "Tipo": [
                        "Queda" if d < 0 else "Alta" for d in ranked["deviation"]
                    ],
                    "No treino": [
                        "Sim" if use_mask[date] else "Não" for date in ranked.index
                    ],
                    "Pontuação": ranked["score"].round(2),
                }
            )
            st.dataframe(an_view, hide_index=True, use_container_width=True)

# ---------------- Decomposição sazonal ----------------
with tab_decomp:
    if decomp_error:
        st.info(decomp_error)
    else:
        fig_dec = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=(
                "Observado e tendência",
                "Componente sazonal",
                "Resíduo",
            ),
        )
        fig_dec.add_trace(
            go.Scatter(
                x=decomp.index,
                y=decomp["observed"],
                name="Observado",
                mode="lines",
                line=dict(color=COLOR_OBSERVED, width=2),
            ),
            row=1,
            col=1,
        )
        fig_dec.add_trace(
            go.Scatter(
                x=decomp.index,
                y=decomp["trend"],
                name="Tendência",
                mode="lines",
                line=dict(color=COLOR_FORECAST, width=3),
            ),
            row=1,
            col=1,
        )
        fig_dec.add_trace(
            go.Scatter(
                x=decomp.index,
                y=decomp["seasonal"],
                name="Sazonalidade",
                mode="lines",
                line=dict(color=SERIES_COLORS[2], width=2),
            ),
            row=2,
            col=1,
        )
        fig_dec.add_trace(
            go.Scatter(
                x=decomp.index,
                y=decomp["resid"],
                name="Resíduo",
                mode="lines",
                line=dict(color=COLOR_MUTED, width=1.5),
            ),
            row=3,
            col=1,
        )
        fig_dec.update_layout(
            title=f"Decomposição — {ml_title}",
            height=640,
            hovermode="x unified",
            separators=",.",
            legend=dict(orientation="h", y=-0.08, x=0),
            margin=dict(l=10, r=10, t=75, b=10),
        )
        fig_dec.update_xaxes(tickformat="%m/%Y", hoverformat="%m/%Y")
        st.plotly_chart(fig_dec, use_container_width=True)

        seasonal_by_month = decomp.groupby(decomp.index.month)["seasonal"].first()
        if decomp_multiplicative:
            effect = (seasonal_by_month - 1) * 100
            effect_title = "Efeito sazonal sobre a tendência (%)"
            effect_text = [pct_text(v, signed=True) for v in effect]
        else:
            effect = seasonal_by_month
            effect_title = f"Efeito sazonal ({ml_metric_axis})"
            effect_text = [f"{v:,.0f}" for v in effect]

        fig_season = go.Figure(
            go.Bar(
                x=[MONTH_NAMES[m - 1] for m in effect.index],
                y=effect.to_numpy(),
                marker_color=COLOR_OBSERVED,
                text=effect_text,
                textposition="outside",
                cliponaxis=False,
            )
        )
        fig_season.update_layout(
            title="Perfil sazonal por mês do ano",
            height=380,
            separators=",.",
            margin=dict(l=10, r=10, t=55, b=10),
        )
        fig_season.update_xaxes(type="category")
        fig_season.update_yaxes(title_text=effect_title, zeroline=True)
        st.plotly_chart(fig_season, use_container_width=True)

        st.caption(
            "Decomposição clássica por média móvel centrada de 12 meses, no "
            + (
                "modo multiplicativo (a sazonalidade é proporcional ao nível)."
                if decomp_multiplicative
                else "modo aditivo (a série tem valores zero)."
            )
            + " Nos extremos da série a tendência é repetida a partir do "
            "último valor calculado. Os meses fora do treino não entram no "
            "cálculo do perfil sazonal."
        )

# ---------------- Agrupamento de rotas ----------------
with tab_cluster:
    route_period = period_data["rota"]
    n_route_months = (
        route_period["data_emissao_bilhete_dt"].nunique()
        if not route_period.empty
        else 0
    )

    if route_period.empty:
        st.warning("O agrupamento de rotas depende da tabela de rotas.")
    elif n_route_months < 12:
        st.info(
            "Selecione na lateral um período de ao menos 12 meses para "
            "agrupar as rotas."
        )
    else:
        cl1, cl2 = st.columns(2)
        with cl1:
            n_groups = st.slider("Número de grupos", 2, 8, 4)
        with cl2:
            min_months = st.slider(
                "Mínimo de meses com registro da rota",
                6,
                n_route_months,
                min(24, max(6, n_route_months // 2)),
            )

        try:
            clusters = ml.cluster_routes(route_period, n_groups, min_months)
        except ValueError as exc:
            st.info(str(exc))
        else:
            routes_df = clusters["routes"]
            best_k = max(
                clusters["silhouette_by_k"], key=clusters["silhouette_by_k"].get
            )
            sil = clusters["silhouette"]

            g1, g2, g3 = st.columns(3)
            g1.metric("Rotas analisadas", br_number(clusters["n_routes"]))
            g2.metric("Silhueta", f"{sil:.2f}".replace(".", ","))
            g3.metric("k sugerido pela silhueta", str(best_k))

            fig_cl = go.Figure()
            for position, group_id in enumerate(sorted(routes_df["grupo"].unique())):
                part = routes_df[routes_df["grupo"] == group_id]
                profile = part["perfil"].iloc[0]
                fig_cl.add_trace(
                    go.Scatter(
                        x=part["pc1"],
                        y=part["pc2"],
                        name=f"Grupo {group_id} — {profile}",
                        mode="markers",
                        marker=dict(
                            color=SERIES_COLORS[position % len(SERIES_COLORS)],
                            size=9,
                            line=dict(width=1, color="white"),
                        ),
                        text=part["rota_unica"],
                        customdata=list(
                            zip(part["media_mensal"], part["ticket_medio"])
                        ),
                        hovertemplate=(
                            "<b>%{text}</b><br>"
                            f"Grupo {group_id}<br>"
                            "Bilhetes/mês: %{customdata[0]:,.0f}<br>"
                            "Ticket médio: R$ %{customdata[1]:,.2f}"
                            "<extra></extra>"
                        ),
                    )
                )
            fig_cl.update_layout(
                title="Mapa de rotas (projeção PCA em 2 dimensões)",
                height=520,
                separators=",.",
                legend=dict(orientation="h", y=-0.15, x=0),
                margin=dict(l=10, r=10, t=55, b=10),
            )
            fig_cl.update_xaxes(title_text="Componente 1")
            fig_cl.update_yaxes(title_text="Componente 2")
            st.plotly_chart(fig_cl, use_container_width=True)

            if sil >= 0.5:
                reading = "grupos bem separados"
            elif sil >= 0.25:
                reading = "separação moderada entre os grupos"
            else:
                reading = (
                    "separação fraca: os perfis de rota formam mais um "
                    "contínuo do que grupos distintos"
                )
            st.caption(
                f"Silhueta de {sil:.2f}".replace(".", ",")
                + f" ({reading}). A projeção em 2D explica "
                + pct_text(clusters["explained"] * 100)
                + " da variação das características. Cada rota é descrita "
                "por volume médio mensal, ticket médio, variação mensal e "
                "pico sazonal. Como a tabela de rotas traz só as rotas mais "
                "movimentadas de cada mês, as médias consideram apenas os "
                "meses em que a rota aparece."
            )

            summary = clusters["summary"].rename(
                columns={
                    "grupo": "Grupo",
                    "perfil": "Perfil",
                    "rotas": "Rotas",
                    "media_mensal": "Bilhetes/mês (média)",
                    "ticket_medio": "Ticket médio (R$)",
                    "cv": "Variação mensal",
                    "pico_sazonal": "Pico sazonal",
                }
            )[
                [
                    "Grupo",
                    "Perfil",
                    "Rotas",
                    "Bilhetes/mês (média)",
                    "Ticket médio (R$)",
                    "Variação mensal",
                    "Pico sazonal",
                ]
            ]
            st.dataframe(
                summary,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Bilhetes/mês (média)": st.column_config.NumberColumn(
                        format="%.0f"
                    ),
                    "Ticket médio (R$)": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "Variação mensal": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "Pico sazonal": st.column_config.NumberColumn(format="%.2f"),
                },
            )

            with st.expander("Rotas por grupo"):
                routes_view = routes_df[
                    [
                        "rota_unica",
                        "grupo",
                        "perfil",
                        "media_mensal",
                        "ticket_medio",
                        "meses",
                    ]
                ].rename(
                    columns={
                        "rota_unica": "Rota",
                        "grupo": "Grupo",
                        "perfil": "Perfil",
                        "media_mensal": "Bilhetes/mês (média)",
                        "ticket_medio": "Ticket médio (R$)",
                        "meses": "Meses com registro",
                    }
                )
                st.dataframe(
                    routes_view,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Bilhetes/mês (média)": st.column_config.NumberColumn(
                            format="%.0f"
                        ),
                        "Ticket médio (R$)": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                    },
                )


# ============================================================
# 12. NOTAS METODOLÓGICAS E FONTE
# ============================================================
with st.expander("Notas metodológicas"):
    st.markdown(
        """
        - Sem filtros laterais, os KPIs e a visão geral da série temporal
          vêm da tabela `tabela_data_viagem_geral.csv`.
        - Com um filtro em uma dimensão, os cards usam a soma das categorias
          selecionadas na tabela daquela dimensão (valor exato). Com filtros
          em duas ou mais dimensões, os cards mostram uma estimativa pelo
          produto das participações, assumindo independência.
        - O percentual de antecedência zero só é afetado pelo filtro de
          meses de antecedência.
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
        - Os filtros de dimensão atuam sobre o gráfico da dimensão
          correspondente e sobre os cards.
        - As tabelas agregadas separadamente não permitem cruzar, por
          exemplo, UF de origem + UF de destino + tipo de tarifa como se
          fossem registros individuais de bilhetes.
        - O gráfico de rotas depende da existência da tabela de rotas e das
          colunas `data_emissao_bilhete`, `rota_unica` e `total_bilhetes`.
        - Machine learning (arquivo `ml.py`): a previsão compara uma
          regressão com tendência e sazonalidade contra o modelo sazonal
          ingênuo ajustado, escolhe por backtest nos últimos 12 meses
          válidos e mostra faixa de 80%. As anomalias usam Isolation Forest
          e o agrupamento de rotas usa K-Means.
        - Meses da pandemia (03/2020 a 12/2021) e meses finais com carga
          possivelmente incompleta podem ser excluídos do treino pelos
          controles da seção de machine learning.
        - As previsões são projeções estatísticas do histórico agregado e
          não consideram mudanças de regulação, preços ou eventos externos.
        """
    )

st.caption(
    "Fonte: dados de bilhetagem Monitriip/ANTT disponibilizados no "
    "repositório do projeto."
)
