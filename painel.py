import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from datetime import datetime

# ======================
# 🔐 CONFIGURAÇÃO
# ======================
API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]

td = TDClient(apikey=API_KEY)

ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

st.set_page_config(layout="wide")
st.title("📊 ROBÔ DAY TRADE FINAL (PRO)")

# ======================
# 📥 DADOS DE MERCADO
# ======================
@st.cache_data(ttl=240)
def pegar_dados(ativo):
    try:
        df = td.time_series(
            symbol=ativo,
            interval="5min",
            outputsize=300
        ).as_pandas()

        df = df[::-1].reset_index(drop=True)

        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.dropna()

    except Exception as e:
        st.error(f"Erro {ativo}: {e}")
        return None

# ======================
# 📰 NOTÍCIAS
# ======================
@st.cache_data(ttl=300)
def pegar_noticias():
    try:
        url = f"https://newsapi.org/v2/everything?q=forex OR USD OR EUR OR GBP&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API}"
        return requests.get(url).json()["articles"]
    except:
        return []

# ======================
# 🧠 ESTRATÉGIA FINAL
# ======================
def analisar(df):
    df["MA9"] = SMAIndicator(df["close"], 9).sma_indicator()
    df["MA21"] = SMAIndicator(df["close"], 21).sma_indicator()

    preco = df["close"].iloc[-1]
    ma9 = df["MA9"].iloc[-1]
    ma21 = df["MA21"].iloc[-1]

    suporte = df["low"].rolling(20).min().iloc[-1]
    resistencia = df["high"].rolling(20).max().iloc[-1]

    lateral = abs(ma9 - ma21) < 0.00015

    if lateral:
        return "AGUARDAR", preco, 0, 0

    # 🔥 COMPRA
    if ma9 > ma21 and preco <= suporte * 1.001:
        stop = suporte
        alvo = preco + (preco - stop) * 2
        return "COMPRA", preco, stop, alvo

    # 🔥 VENDA
    if ma9 < ma21 and preco >= resistencia * 0.999:
        stop = resistencia
        alvo = preco - (stop - preco) * 2
        return "VENDA", preco, stop, alvo

    return "AGUARDAR", preco, 0, 0

# ======================
# 📊 PAINEL
# ======================
col1, col2, col3 = st.columns(3)

for i, ativo in enumerate(ativos):
    with [col1, col2, col3][i]:
        st.subheader(ativo)

        df = pegar_dados(ativo)

        if df is not None:
            sinal, preco, stop, alvo = analisar(df)

            st.metric("Preço", f"{preco:.5f}")

            if sinal == "COMPRA":
                st.success("🟢 COMPRA CONFIRMADA")
                st.write("Stop:", stop)
                st.write("Alvo:", alvo)

            elif sinal == "VENDA":
                st.error("🔴 VENDA CONFIRMADA")
                st.write("Stop:", stop)
                st.write("Alvo:", alvo)

            else:
                st.info("⚪ AGUARDAR")

# ======================
# 📰 NOTÍCIAS
# ======================
st.divider()
st.subheader("📰 Notícias Forex em tempo real")

news = pegar_noticias()

for n in news:
    st.write("🗞️", n["title"])
