import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import datetime

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô estável", layout="wide")
st.title("🤖 Robô estável")

ATIVO = "EUR/USD"

@st.cache_data(ttl=120)
def pegar_dados():
    df = td.time_series(
        symbol=ATIVO,
        interval="5min",
        outputsize=2000
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# ESTRATÉGIA SIMPLES
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    preco = df["close"].iloc[-1]

    sup = df["low"].tail(50).min()

    score = 0
    erros = []

    # tendência simples
    if df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        score += 1
        trend = "ALTA"
    else:
        trend = "BAIXA"

    # RSI simples
    rsi = df["RSI"].iloc[-1]

    if trend == "ALTA" and rsi < 70:
        score += 1
    elif trend == "BAIXA" and rsi > 30:
        score += 1
    else:
        erros.append(f"RSI fora ({rsi:.2f})")

    # suporte simples
    if abs(preco - sup) < sup * 0.01:
        score += 1
    else:
        erros.append("Longe suporte")

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if score >= 2:
        return "COMPRA" if trend == "ALTA" else "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST SIMPLES
# ======================

def backtest(df):

    wins = 0
    loss = 0
    logs = []

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    for i in range(100, len(df)-1):

        ema9 = df["EMA9"].iloc[i]
        ema21 = df["EMA21"].iloc[i]
        rsi = df["RSI"].iloc[i]

        preco = df["close"].iloc[i]
        saida = df["close"].iloc[i+1]

        trend = "ALTA" if ema9 > ema21 else "BAIXA"

        if trend == "ALTA" and rsi < 70:
            if saida > preco:
                wins += 1
            else:
                loss += 1

        elif trend == "BAIXA" and rsi > 30:
            if saida < preco:
                wins += 1
            else:
                loss += 1

    return wins, loss

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("Preço", preco)

st.write("Sinal:", sinal)

st.write("Erros:", erros)

if st.button("Backtest"):
    w, l = backtest(df)
    total = w + l
    st.write("Wins:", w)
    st.write("Loss:", l)
    st.write("Winrate:", (w/total*100 if total else 0))
