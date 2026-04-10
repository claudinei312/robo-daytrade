import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
import time
from streamlit_autorefresh import st_autorefresh
from ta.momentum import RSIIndicator

# ======================
# 🎨 LAYOUT
# ======================

st.set_page_config(page_title="Sniper Pro Trading", layout="wide")

st.markdown("""

<style>  
body { background-color: #0b0f19; }  
  
.main-title {  
    font-size: 34px;  
    font-weight: 800;  
    text-align: center;  
    color: #00ff99;  
    margin-bottom: 15px;  
}  
  
div[data-testid="stMetric"] {  
    background-color: #0f172a;  
    border-radius: 10px;  
    padding: 8px;  
}  
</style>  """, unsafe_allow_html=True)

st.markdown("<div class='main-title'>📊 SNIPER PRO TRADING DESK</div>", unsafe_allow_html=True)

# ======================
# 🔐 CONFIG
# ======================

API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]
BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

td = TDClient(apikey=API_KEY)

ativos = ["USD/JPY:FX"]

st_autorefresh(interval=5000, key="refresh")

rodando = st.toggle("🟢 Ativar Robô", value=True)

if not rodando:
    st.stop()

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
        outputsize=300
    ).as_pandas()

    df = df[::-1].reset_index()

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["datetime"] = df["datetime"].dt.tz_localize("UTC")
    df["datetime"] = df["datetime"].dt.tz_convert("America/Sao_Paulo")

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 ESTRATÉGIA (🔥 MELHORADA)
# ======================

def analisar(df):

    df["MA9"] = SMAIndicator(df["close"], 9).sma_indicator()
    df["MA21"] = SMAIndicator(df["close"], 21).sma_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    preco = df["close"].iloc[-1]
    ma9 = df["MA9"].iloc[-1]
    ma21 = df["MA21"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    suporte = df["low"].rolling(20).min().iloc[-1]
    resistencia = df["high"].rolling(20).max().iloc[-1]

    # tendência real mais forte
    tendencia = abs(ma9 - ma21) > 0.00025

    # candle forte
    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]
    candle = body > rng * 0.6

    # volatilidade
    vol = df["high"].rolling(10).max().iloc[-1] - df["low"].rolling(10).min().iloc[-1]
    vol_ok = vol > preco * 0.0005

    # 🔥 FILTRO RSI (NOVO)
    rsi_ok_buy = rsi < 70
    rsi_ok_sell = rsi > 30

    # ======================
    # ❌ FILTROS GERAIS
    # ======================
    if not tendencia or not candle or not vol_ok:
        return "AGUARDAR", preco, 0, 0

    # ======================
    # 🟢 COMPRA (melhorada)
    # ======================
    if (
        ma9 > ma21 and
        preco <= suporte * 1.001 and
        rsi_ok_buy
    ):
        return "COMPRA", preco, suporte, preco + (preco - suporte) * 2

    # ======================
    # 🔴 VENDA (melhorada)
    # ======================
    if (
        ma9 < ma21 and
        preco >= resistencia * 0.999 and
        rsi_ok_sell
    ):
        return "VENDA", preco, resistencia, preco - (resistencia - preco) * 2

    return "AGUARDAR", preco, 0, 0

# ======================
# 🔁 DADOS
# ======================

dados = {ativo: pegar_dados(ativo) for ativo in ativos}

# ======================
# 📊 LOOP PRINCIPAL (INALTERADO)
# ======================

for ativo in ativos:

    st.markdown("---")

    df = dados[ativo]
    sinal, preco, stop, alvo = analisar(df)
    agora = datetime.datetime.now()

    st.subheader(ativo)
    st.metric("Preço", preco)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"]
    ))

    fig.update_layout(template="plotly_dark", height=420, xaxis_rangeslider_visible=False)

    st.plotly_chart(fig, use_container_width=True)

    if sinal == "COMPRA":
        st.success("🟢 COMPRA")

    elif sinal == "VENDA":
        st.error("🔴 VENDA")

    else:
        st.info("⚪ AGUARDAR")

    if sinal in ["COMPRA", "VENDA"]:

        telegram(f"""
🚨 SNIPER PRO TRADE

📊 Ativo: {ativo}
📈 Sinal: {sinal}

💰 Preço: {preco}
🎯 Alvo: {alvo}

⏱ {agora.strftime('%H:%M:%S')}
""")
