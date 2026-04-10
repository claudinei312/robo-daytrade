import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator

# ======================
# 🔐 CONFIG
# ======================
API_KEY = st.secrets["API_KEY"]
BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

td = TDClient(apikey=API_KEY)

ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

# ======================
# 🎨 LAYOUT
# ======================
st.set_page_config(page_title="Sniper Pro", layout="wide")

st.markdown("""
<style>
.big-title {
    font-size:32px;
    font-weight:700;
    color:#00ff99;
    text-align:center;
}
.card {
    background:#111827;
    padding:15px;
    border-radius:12px;
    margin-bottom:10px;
    border:1px solid #2d2d2d;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='big-title'>📊 SNIPER PRO DASHBOARD</div>", unsafe_allow_html=True)

# ======================
# 📩 TELEGRAM
# ======================
def telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ======================
# 📥 DADOS
# ======================
@st.cache_data(ttl=240)
def pegar_dados(ativo):
    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=200
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 SNIPER
# ======================
def analisar(df):

    df["MA9"] = SMAIndicator(df["close"], 9).sma_indicator()
    df["MA21"] = SMAIndicator(df["close"], 21).sma_indicator()

    preco = df["close"].iloc[-1]
    ma9 = df["MA9"].iloc[-1]
    ma21 = df["MA21"].iloc[-1]

    suporte = df["low"].rolling(20).min().iloc[-1]
    resistencia = df["high"].rolling(20).max().iloc[-1]

    tendencia = abs(ma9 - ma21) > 0.00025

    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]

    candle = body > rng * 0.6

    vol = df["high"].rolling(10).max().iloc[-1] - df["low"].rolling(10).min().iloc[-1]
    vol_ok = vol > preco * 0.0005

    if not tendencia or not candle or not vol_ok:
        return "AGUARDAR", preco, 0, 0

    if ma9 > ma21 and preco <= suporte * 1.001:
        return "COMPRA", preco, suporte, preco + (preco - suporte) * 2

    if ma9 < ma21 and preco >= resistencia * 0.999:
        return "VENDA", preco, resistencia, preco - (resistencia - preco) * 2

    return "AGUARDAR", preco, 0, 0

# ======================
# 📩 FORMATAÇÃO TELEGRAM
# ======================
def formatar_sinal(ativo, sinal, preco, stop, alvo):

    if sinal == "COMPRA":
        return f"""
🟢 COMPRA DETECTADA
📊 {ativo}
💰 {preco}
🛑 SL {stop}
🎯 TP {alvo}
"""

    if sinal == "VENDA":
        return f"""
🔴 VENDA DETECTADA
📊 {ativo}
💰 {preco}
🛑 SL {stop}
🎯 TP {alvo}
"""

    return ""

# ======================
# 📊 BOTÃO LIGA/DESLIGA
# ======================
rodando = st.toggle("🟢 Robô Ativo", value=True)

if not rodando:
    st.stop()

# ======================
# 📊 PAINEL
# ======================
col1, col2, col3 = st.columns(3)

for i, ativo in enumerate(ativos):

    with [col1, col2, col3][i]:

        df = pegar_dados(ativo)

        sinal, preco, stop, alvo = analisar(df)

        st.markdown(f"<div class='card'><b>{ativo}</b><br>Preço: {preco}<br>Sinal: {sinal}</div>", unsafe_allow_html=True)

        if sinal == "COMPRA":
            st.success("🟢 COMPRA")
            telegram(formatar_sinal(ativo, sinal, preco, stop, alvo))

        elif sinal == "VENDA":
            st.error("🔴 VENDA")
            telegram(formatar_sinal(ativo, sinal, preco, stop, alvo))

        else:
            st.info("⚪ AGUARDAR")
