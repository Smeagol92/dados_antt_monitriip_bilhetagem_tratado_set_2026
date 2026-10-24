import streamlit as st  # <-- Garanta que está exatamente assim
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página para aproveitar toda a largura da tela
st.set_page_config(page_title="Dashboard de Bilhetagem e Faturamento", layout="wide")

# 1. Carregamento Otimizado de Dados
@st.cache_data  # <-- Agora o 'st' vai funcionar perfeitamente aqui!

def carregar_dados_otimizado():
    # 1. INSIRA O SEU ID DO GOOGLE DRIVE AQUI
    ID_DO_ARQUIVO = "1qCIIRdV1ZogQUOvM2Wn2ViSCWfe9716t"
    
    # Monta a URL de download direto aceita pelo Pandas
    url_direta = f"https://drive.google.com/uc?export=download&id={ID_DO_ARQUIVO}"
    
    colunas_necessarias = [
        'data_emissao_bilhete', 'rota_unica', 'tipo_servico',
        'quantidade_bilhetes', 'valor_total', 'tipo_tarifa', 'meses_antecedencia'
    ]
    
    # O pandas lê a URL direta usando o pyarrow de forma transparente
    df = pd.read_parquet(
        url_direta, 
        engine="pyarrow", 
        columns=colunas_necessarias
    )
    
    df['data_emissao_bilhete'] = pd.to_datetime(df['data_emissao_bilhete'])
    
    return df
