import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
import time
from streamlit_autorefresh import st_autorefresh

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
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>📊 SNIPER PRO TRADING DESK</div>", unsafe_allow_html=True)

# ======================
# 🔐 CONFIG
# ======================
API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]
BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

td = TDClient(apikey=API_KEY)

ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

# ======================
# 🔁 AUTO REFRESH
# ======================
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
# ⏱️ TIMER
# ======================
def tempo_candle():
    agora = datetime.datetime.utcnow()
    minuto = agora.minute % 5
    segundo = agora.second
    return f"{4 - minuto:02d}:{59 - segundo:02d}"

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
# 🧠 ESTRATÉGIA (SEM ALTERAÇÃO)
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
# 🧠 ESTADO GLOBAL
# ======================
if "sinais" not in st.session_state:
    st.session_state.sinais = {}

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

    # ======================
    # REGISTRAR SINAL
    # ======================
    if sinal in ["COMPRA", "VENDA"]:

        if ativo not in st.session_state.sinais or st.session_state.sinais[ativo]["tipo"] != sinal:

            st.session_state.sinais[ativo] = {
                "tipo": sinal,
                "entrada_hora": agora,
                "preco_entrada": preco,
                "preco_saida": alvo
            }

            agora_txt = agora.strftime("%H:%M:%S")

            telegram(f"""
📊 SINAL {ativo}
Direção: {sinal}

💰 Entrada: {preco}
🎯 Saída: {alvo}

🟢 Hora entrada: {agora_txt}
🔴 Saída estimada: +5min
""")

    # ======================
    # EXIBIÇÃO
    # ======================
    st.subheader(ativo)

    st.metric("Preço", preco)
    st.info(f"⏱ Candle fecha em: {tempo_candle()}")

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
    # PAINEL DO SINAL
    # ======================
    info = st.session_state.sinais.get(ativo, None)

    if info:

        entrada = info["entrada_hora"]
        saida = entrada + datetime.timedelta(minutes=5)

        st.markdown("### 📊 SINAL DO ATIVO")

        st.write(f"📌 Direção: {info['tipo']}")
        st.write(f"💰 Preço de entrada: {info['preco_entrada']}")
        st.write(f"🎯 Preço de saída: {info['preco_saida']}")
        st.write(f"🟢 Hora entrada: {entrada.strftime('%H:%M:%S')}")
        st.write(f"🔴 Hora saída: {saida.strftime('%H:%M:%S')}")

    else:
        st.info("📌 Possível entrada: AGUARDAR")

    # ======================
    # ALERTA
    # ======================
    if sinal == "COMPRA":
        st.success("🟢 COMPRA")

    elif sinal == "VENDA":
        st.error("🔴 VENDA")

    else:
        st.info("⚪ AGUARDAR")

# ======================
# 📰 NOTÍCIAS
# ======================
st.divider()
st.subheader("📰 Notícias")

for n in noticias():
    st.write("🗞️", n["title"])
