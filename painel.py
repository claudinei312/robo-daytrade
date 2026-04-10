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
BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

td = TDClient(apikey=API_KEY)

ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

st.set_page_config(layout="wide")
st.title("📊 ROBÔ SNIPER + BACKTEST AUTOMÁTICO")

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
# 📰 NOTÍCIAS (FILTRO RISCO)
# ======================
@st.cache_data(ttl=300)
def noticias():
    url = f"https://newsapi.org/v2/everything?q=forex OR USD OR EUR OR GBP&language=en&pageSize=5&apiKey={NEWS_API}"
    try:
        return requests.get(url).json()["articles"]
    except:
        return []

def mercado_perigoso():
    palavras = ["interest rate", "inflation", "fed", "crisis", "war", "recession"]

    for n in noticias():
        titulo = n["title"].lower()
        if any(p in titulo for p in palavras):
            return True
    return False

# ======================
# 🧠 MELHOR ATIVO DO DIA
# ======================
def melhor_ativo(dados):

    scores = {}

    for ativo, df in dados.items():

        vol = df["high"].rolling(20).max().iloc[-1] - df["low"].rolling(20).min().iloc[-1]

        ma9 = SMAIndicator(df["close"], 9).sma_indicator().iloc[-1]
        ma21 = SMAIndicator(df["close"], 21).sma_indicator().iloc[-1]

        trend = abs(ma9 - ma21)

        scores[ativo] = vol + trend

    return max(scores, key=scores.get)

# ======================
# 📊 BACKTEST AUTOMÁTICO 08h–12h
# ======================
def backtest_hoje(df):

    wins = 0
    losses = 0
    trades = 0

    for i in range(50, len(df)):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora >= 12:
            continue

        sinal, preco, stop, alvo = analisar(df)

        if sinal == "COMPRA":
            trades += 1
            if df["high"].iloc[i:].max() >= alvo:
                wins += 1
            else:
                losses += 1

        if sinal == "VENDA":
            trades += 1
            if df["low"].iloc[i:].min() <= alvo:
                wins += 1
            else:
                losses += 1

    winrate = (wins / trades * 100) if trades > 0 else 0

    return trades, wins, losses, winrate

# ======================
# 📥 DADOS GERAIS
# ======================
dados = {}

for ativo in ativos:
    dados[ativo] = pegar_dados(ativo)

# ======================
# 🚨 BLOQUEIO POR NOTÍCIA
# ======================
if mercado_perigoso():
    st.error("⚠️ MERCADO PERIGOSO HOJE")
    telegram("⚠️ Mercado em risco hoje (notícias fortes)")
    st.stop()

# ======================
# 🏆 MELHOR ATIVO
# ======================
best = melhor_ativo(dados)

st.subheader("🏆 Melhor ativo do dia")
st.success(best)

# ======================
# 📊 PAINEL AO VIVO
# ======================
col1, col2, col3 = st.columns(3)

for i, ativo in enumerate(ativos):

    with [col1, col2, col3][i]:

        st.subheader(ativo)

        df = dados[ativo]

        sinal, preco, stop, alvo = analisar(df)

        st.metric("Preço", preco)

        if ativo == best:
            st.info("🔥 Melhor ativo hoje")

        if sinal == "COMPRA":
            st.success("🟢 COMPRA")
            telegram(f"🟢 COMPRA {ativo} | {preco} | SL {stop} | TP {alvo}")

        elif sinal == "VENDA":
            st.error("🔴 VENDA")
            telegram(f"🔴 VENDA {ativo} | {preco} | SL {stop} | TP {alvo}")

        else:
            st.info("⚪ AGUARDAR")

# ======================
# 📊 BACKTEST AUTOMÁTICO (DIA)
# ======================
st.divider()
st.subheader("📊 BACKTEST AUTOMÁTICO 08h–12h (HOJE)")

for ativo in ativos:

    df = dados[ativo]

    trades, wins, losses, winrate = backtest_hoje(df)

    st.write(f"""
    **{ativo}**  
    Trades: {trades}  
    Wins: {wins}  
    Losses: {losses}  
    Winrate: {winrate:.2f}%  
    """)

    if winrate > 55:
        st.success("🟢 DIA BOM PARA ESSE ATIVO")
    else:
        st.warning("⚠️ DIA FRACO PARA ESSE ATIVO")
