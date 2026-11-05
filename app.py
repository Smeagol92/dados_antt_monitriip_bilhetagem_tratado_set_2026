import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Dashboard ANTT | Monitriip",
    page_icon="🚌",
    layout="wide",
)

st.title("🚌 Dashboard ANTT | Bilhetagem Monitriip")
st.caption(
    "Análise histórica de bilhetes, arrecadação, tarifas, serviços e "
    "características das viagens."
)

BASE_RAW_URL = (
    "https://raw.githubusercontent.com/"
    "Smeagol92/dados_antt_monitriip_bilhetagem_tratado_set_2026/"
    "main/data/"
)

# A tabela de rotas é opcional: o arquivo rota_unica informado na versão
# anterior não foi localizado no caminho esperado do repositório.
ARQUIVOS = {
    "geral": "tabela_data_viagem_geral.csv",
    "destino_uf": "tabela_ponto_destino_viagem_uf.csv",
    "origem_uf": "tabela_ponto_origem_viagem_uf.csv",
    "tarifa": "tabela_tipo_tarifa.csv",
    "nacionalidade": "tabela_nacional_internacional.csv",
    "antecedencia": "tabela_meses_antecedencia.csv",
    "ambito": "tabela_estadual_interestadual.csv",
    "gratuidade": "tabela_tipo_gratuidade.csv",
    "servico": "tabela_tipo_servico.csv",
    "rota_unica": "tabela_rota_unica.csv",  # opcional
}

COLUNAS_DIMENSAO = {
    "destino_uf": "ponto_destino_viagem_uf",
    "origem_uf": "ponto_origem_viagem_uf",
    "tarifa": "tipo_tarifa",
    "nacionalidade": "nacional_internacional",
    "antecedencia": "meses_antecedencia",
    "ambito": "estadual_interestadual",
    "gratuidade": "tipo_gratuidade",
    "servico": "tipo_servico",
    "rota_unica": "rota_unica",
}

COLUNAS_OBRIGATORIAS = {
    "geral": ["data_viagem", "total_bilhetes", "total_arrecadacao"],
    "destino_uf": [
        "data_viagem", "ponto_destino_viagem_uf", "total_bilhetes"
    ],
    "origem_uf": [
        "data_viagem", "ponto_origem_viagem_uf", "total_bilhetes"
    ],
    "tarifa": ["data_viagem", "tipo_tarifa", "total_bilhetes"],
    "nacionalidade": [
        "data_viagem", "nacional_internacional", "total_bilhetes"
    ],
    "antecedencia": [
        "data_viagem", "meses_antecedencia", "total_bilhetes"
    ],
    "ambito": [
        "data_viagem", "estadual_interestadual", "total_bilhetes"
    ],
    "gratuidade": [
        "data_viagem", "tipo_gratuidade", "total_bilhetes"
    ],
    "servico": ["data_viagem", "tipo_servico", "total_bilhetes"],
    "rota_unica": ["data_viagem", "rota_unica", "total_bilhetes"],
}

MEDIDAS_NUMERICAS = [
    "total_bilhetes",
    "total_arrecadacao",
    "proporcao_bilhetes",
    "proporcao_arrecadacao",
    "ticket_medio",
]


# ============================================================
# FUNÇÕES DE APOIO
# ============================================================
@st.cache_data(ttl=3600, show_spinner="Carregando bases da ANTT...")
def carregar_dados():
    """Carrega, valida e padroniza os CSVs publicados no GitHub."""
    bases = {}
    avisos = []
