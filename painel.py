import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
from datetime import datetime

# ======================
# 🔐 CONFIG
# ======================
API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]

td = TDClient(apikey=API_KEY)

ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

st.set_page_config(layout="wide")
st.title("📊 ROBÔ DAY TRADE PRO")

# ======================
# 🟢 LIGA / DESLIGA
# ======================
rodando = st.toggle("🟢 Ativar Robô", value=True)

if not rodando:
    st.warning("⛔ Robô pausado")
    st.stop()

# ======================
# 🕐 PRÓXIMA VELA M5
# ======================
def proxima_vela_m5():
    agora = datetime.now()

    minuto = (agora.minute // 5 + 1) * 5
    hora = agora.hour

    if minuto == 60:
        minuto = 0
        hora += 1

    return agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

entrada = proxima_vela_m5()

# ======================
# 📥 DADOS
# ======================
@st.cache_data(ttl=240)
def pegar_dados(ativo):
    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=300
    ).as_pandas()

    df = df[::-1].reset_index(drop=True)

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 📰 NOTÍCIAS
# ======================
@st.cache_data(ttl=300)
def pegar_noticias():
    url = f"https://newsapi.org/v2/everything?q=forex OR USD OR EUR OR GBP&language=en&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API}"
    try:
        return requests.get(url).json()["articles"]
    except:
        return []

# ======================
# 🧠 LÓGICA FINAL
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

    distancia_sup = abs(preco - suporte)
    distancia_res = abs(preco - resistencia)

    # ======================
    # ⚪ AGUARDAR
    # ======================
    if lateral:
        return "AGUARDAR", preco, 0, 0

    if distancia_sup > preco * 0.002 and distancia_res > preco * 0.002:
        return "AGUARDAR", preco, 0, 0

    # ======================
    # 🟡 ALERTA
    # ======================
    if ma9 > ma21 and preco <= suporte * 1.003:
        return "ALERTA_COMPRA", preco, 0, 0

    if ma9 < ma21 and preco >= resistencia * 0.997:
        return "ALERTA_VENDA", preco, 0, 0

    # ======================
    # 🟢 / 🔴 ENTRADA REAL
    # ======================
    if ma9 > ma21 and preco <= suporte * 1.001:
        stop = suporte
        alvo = preco + (preco - stop) * 2
        return "COMPRA", preco, stop, alvo

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

            # ======================
            # VISUAL DOS SINAIS
            # ======================
            if sinal == "AGUARDAR":
                st.info("⚪ AGUARDAR")

            elif "ALERTA" in sinal:
                st.warning("🟡 " + sinal)
                st.write("📍 Preparar entrada:", entrada.strftime("%H:%M"))

            elif sinal == "COMPRA":
                st.success("🟢 COMPRA CONFIRMADA")
                st.write("📍 Entrada:", entrada.strftime("%H:%M"))
                st.write("🛑 Stop:", stop)
                st.write("🎯 Alvo:", alvo)

            elif sinal == "VENDA":
                st.error("🔴 VENDA CONFIRMADA")
                st.write("📍 Entrada:", entrada.strftime("%H:%M"))
                st.write("🛑 Stop:", stop)
                st.write("🎯 Alvo:", alvo)

# ======================
# 📰 NOTÍCIAS
# ======================
st.divider()
st.subheader("📰 Notícias Forex")

for n in pegar_noticias():
    st.write("🗞️", n["title"])
