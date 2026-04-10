import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
import time
from streamlit_autorefresh import st_autorefresh
import json

# ======================
# 🎨 LAYOUT
# ======================
st.set_page_config(page_title="Sniper Pro Trading", layout="wide")

st.markdown("<div style='text-align:center;font-size:28px;font-weight:bold;'>📊 SNIPER PRO TRADING DESK</div>", unsafe_allow_html=True)

# ======================
# 🔐 CONFIG
# ======================
API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]
BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = "7794049342"

td = TDClient(apikey=API_KEY)

# ======================
# 🧠 CONFIG DINÂMICA
# ======================
def carregar_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except:
        return {"ma_fast": 9, "ma_slow": 21}

cfg = carregar_config()
MA_FAST = cfg["ma_fast"]
MA_SLOW = cfg["ma_slow"]

# ======================
# 🎯 ATIVO
# ======================
ativos = ["USD/JPY:FX"]

# ======================
# 🔁 AUTO REFRESH
# ======================
st_autorefresh(interval=5000, key="refresh")

rodando = st.toggle("🟢 Ativar Robô", value=True)

if not rodando:
    st.stop()

# ======================
# 📩 TELEGRAM (CORRIGIDO)
# ======================
def telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }

    try:
        r = requests.post(url, data=payload, timeout=10)

        print("STATUS:", r.status_code)
        print("RESPOSTA:", r.text)

    except Exception as e:
        print("ERRO TELEGRAM:", e)

# ======================
# 🧪 TESTE TELEGRAM
# ======================
if st.button("📩 Testar Telegram"):
    telegram("🚀 TESTE: Telegram funcionando!")
    st.success("Mensagem enviada (verifique o Telegram)")

# ======================
# ⏱️ TIMER
# ======================
def tempo_candle():
    agora = datetime.datetime.utcnow()
    minuto = agora.minute % 5
    segundo = agora.second
    return f"{4 - minuto:02d}:{59 - segundo:02d}"

# ======================
# 📰 NOTÍCIAS
# ======================
@st.cache_data(ttl=300)
def noticias():
    url = f"https://newsapi.org/v2/everything?q=forex OR USD OR JPY&language=en&pageSize=5&apiKey={NEWS_API}"
    try:
        return requests.get(url).json().get("articles", [])
    except:
        return []

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
# 🧠 ESTRATÉGIA
# ======================
def analisar(df):

    df["MA9"] = SMAIndicator(df["close"], MA_FAST).sma_indicator()
    df["MA21"] = SMAIndicator(df["close"], MA_SLOW).sma_indicator()

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
# 🧠 ESTADO
# ======================
if "sinais" not in st.session_state:
    st.session_state.sinais = {}

if "ultimo_status" not in st.session_state:
    st.session_state.ultimo_status = {}

# ======================
# 📥 DADOS
# ======================
dados = {ativo: pegar_dados(ativo) for ativo in ativos}

# ======================
# 📊 LOOP
# ======================
for ativo in ativos:

    st.markdown("---")

    df = dados[ativo]
    sinal, preco, stop, alvo = analisar(df)
    agora = datetime.datetime.now()

    if sinal in ["COMPRA", "VENDA"]:

        if ativo not in st.session_state.sinais or st.session_state.sinais[ativo]["tipo"] != sinal:

            st.session_state.sinais[ativo] = {
                "tipo": sinal,
                "entrada_hora": agora,
                "preco_entrada": preco,
                "preco_saida": alvo
            }

            telegram(f"""
🚨 SINAL DE TRADE

📊 Ativo: {ativo}
📈 Direção: {sinal}

💰 Entrada: {preco}
🎯 Saída: {alvo}

🕒 {agora.strftime('%H:%M:%S')}
""")

    ultimo = st.session_state.ultimo_status.get(ativo)

    if not ultimo or (agora - ultimo).seconds >= 300:

        st.session_state.ultimo_status[ativo] = agora

        telegram(f"""
📊 STATUS

📌 {ativo}
💰 Preço: {preco}
📈 Sinal: {sinal}
""")

    st.subheader(ativo)
    st.metric("Preço", preco)
    st.info(f"⏱ Candle: {tempo_candle()}")

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

# ======================
# 📰 NOTÍCIAS
# ======================
st.divider()
st.subheader("📰 Notícias")

for n in noticias():
    st.write("🗞️", n["title"])
