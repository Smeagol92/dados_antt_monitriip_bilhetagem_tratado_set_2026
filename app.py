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
