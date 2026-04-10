import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
from streamlit_autorefresh import st_autorefresh

# ======================
# 🎨 LAYOUT PROFISSIONAL
# ======================
st.set_page_config(
    page_title="Sniper Pro Trading",
    layout="wide"
)

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

.card {
    background: #111827;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid #1f2937;
    margin-bottom: 10px;
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
# ⏱️ TIMER CANDLE
# ======================
def tempo_candle():

    agora = datetime.datetime.utcnow()

    minuto = agora.minute % 5
    segundo = agora.second

    min_rest = 4 - minuto
    seg_rest = 59 - segundo

    return f"{min_rest:02d}:{seg_rest:02d}"

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
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 📰 NOTÍCIAS
# ======================
@st.cache_data(ttl=300)
def noticias():

    url = f"https://newsapi.org/v2/everything?q=forex OR USD OR EUR OR GBP&language=en&pageSize=5&apiKey={NEWS_API}"

    try:
        return requests.get(url).json()["articles"]
    except:
        return []

# ======================
# 🧠 SNIPER (INALTERADO)
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
# 📊 SCORE MERCADO
# ======================
def score_mercado(dados):

    total = 0

    for ativo, df in dados.items():

        vol = df["high"].rolling(20).max().iloc[-1] - df["low"].rolling(20).min().iloc[-1]
        mov = abs(df["close"].iloc[-1] - df["close"].iloc[-20])

        total += vol + mov

    media = total / len(dados)

    if media < 0.001:
        return "🔴 RUIM"
    elif media < 0.003:
        return "🟡 NEUTRO"
    else:
        return "🟢 BOM"

# ======================
# 📰 RISCO NOTÍCIA
# ======================
def nivel_noticia():

    forte = ["fed", "interest rate", "inflation", "war", "crisis"]
    medio = ["usd", "eur", "gbp"]

    nivel = "🟢 BAIXO"

    for n in noticias():
        t = n["title"].lower()

        if any(x in t for x in forte):
            return "🔴 ALTO RISCO"

        if any(x in t for x in medio):
            nivel = "🟡 MÉDIO"

    return nivel

# ======================
# 🏆 RANKING
# ======================
def ranking_ativos(dados):

    scores = {}

    for ativo, df in dados.items():

        vol = df["high"].rolling(20).max().iloc[-1] - df["low"].rolling(20).min().iloc[-1]
        ma9 = SMAIndicator(df["close"], 9).sma_indicator().iloc[-1]
        ma21 = SMAIndicator(df["close"], 21).sma_indicator().iloc[-1]

        trend = abs(ma9 - ma21)

        scores[ativo] = vol + trend

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

# ======================
# 📊 GRÁFICO CANDLE
# ======================
def grafico(df, ativo):

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing_line_color="green",
        decreasing_line_color="red"
    ))

    fig.update_layout(
        title=f"{ativo} - 5M Candle Live",
        template="plotly_dark",
        height=420,
        xaxis_rangeslider_visible=False
    )

    return fig

# ======================
# 📥 DADOS
# ======================
dados = {ativo: pegar_dados(ativo) for ativo in ativos}

score = score_mercado(dados)
news_level = nivel_noticia()
ranking = ranking_ativos(dados)
best = ranking[0][0]

# ======================
# 🧠 PAINEL GLOBAL
# ======================
st.subheader("🧠 INTELIGÊNCIA DO DIA")

st.write("📊 Mercado:", score)
st.write("📰 Notícias:", news_level)

st.subheader("🏆 Ranking de ativos")

for ativo, sc in ranking:
    st.write(f"{ativo} → {sc:.4f}")

st.success(f"🔥 Melhor ativo do dia: {best}")

# ======================
# 🚨 BLOQUEIO RISCO
# ======================
if news_level == "🔴 ALTO RISCO":
    st.error("⚠️ MERCADO EM ALTO RISCO")
    telegram("⚠️ Mercado perigoso hoje - evitar operações")
    st.stop()

# ======================
# 📊 PAINEL ATIVOS
# ======================
col1, col2, col3 = st.columns(3)

for i, ativo in enumerate(ativos):

    with [col1, col2, col3][i]:

        df = dados[ativo]

        sinal, preco, stop, alvo = analisar(df)

        st.markdown(f"<div class='card'><b>{ativo}</b></div>", unsafe_allow_html=True)

        st.metric("Preço", preco)

        st.info(f"⏱ Próximo candle: {tempo_candle()}")

        st.plotly_chart(grafico(df, ativo), use_container_width=True)

        if ativo == best:
            st.info("🔥 Melhor ativo do dia")

        if sinal == "COMPRA":
            st.success("🟢 COMPRA")
            telegram(f"🟢 COMPRA {ativo} | {preco} | SL {stop} | TP {alvo}")

        elif sinal == "VENDA":
            st.error("🔴 VENDA")
            telegram(f"🔴 VENDA {ativo} | {preco} | SL {stop} | TP {alvo}")

        else:
            st.info("⚪ AGUARDAR")

# ======================
# 📰 NOTÍCIAS
# ======================
st.divider()
st.subheader("📰 Notícias")

for n in noticias():
    st.write("🗞️", n["title"])
