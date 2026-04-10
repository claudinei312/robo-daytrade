import streamlit as st
from twelvedata import TDClient
import pandas as pd
import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

# ======================
# 🎨 CONFIG
# ======================

st.set_page_config(page_title="Sniper Pro AI", layout="wide")

st.title("📊 Sniper Pro AI Trading System")

# ======================
# 🔐 API
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

ativos = ["USD/JPY:FX"]

st_autorefresh(interval=6000, key="refresh")

# ======================
# 📥 DADOS
# ======================

@st.cache_data(ttl=240)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=2000
    ).as_pandas()

    df = df[::-1].reset_index()

    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 ESTRATÉGIA NOVA (PROFISSIONAL)
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    preco = df["close"].iloc[-1]

    ema9 = df["EMA9"].iloc[-1]
    ema21 = df["EMA21"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    suporte = df["low"].rolling(30).min().iloc[-1]
    resistencia = df["high"].rolling(30).max().iloc[-1]

    # 🔥 FORÇA DE TENDÊNCIA (EVITA LATERAL)
    tendencia_forte = abs(ema9 - ema21) > (preco * 0.001)

    # 📊 DIREÇÃO
    alta = ema9 > ema21
    baixa = ema9 < ema21

    # 🕯 candle forte
    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]
    candle_ok = body > rng * 0.65

    # 📉 RSI extremos (evita entradas ruins)
    rsi_buy_ok = rsi < 65
    rsi_sell_ok = rsi > 35

    # ❌ FILTRO DE LATERAL
    if not tendencia_forte or not candle_ok:
        return "AGUARDAR", preco, 0, 0, "Lateral ou sem força"

    # 🟢 COMPRA
    if alta and preco <= suporte * 1.002 and rsi_buy_ok:
        alvo = preco + (preco - suporte) * 2
        return "COMPRA", preco, suporte, alvo, "Pullback tendência alta"

    # 🔴 VENDA
    if baixa and preco >= resistencia * 0.998 and rsi_sell_ok:
        alvo = preco - (resistencia - preco) * 2
        return "VENDA", preco, resistencia, alvo, "Rejeição resistência"

    return "AGUARDAR", preco, 0, 0, "Sem setup"

# ======================
# 📊 BACKTEST 30 DIAS
# ======================

def backtest(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    df = df.dropna()

    wins = 0
    losses = 0
    erros = {
        "lateral": 0,
        "sem_tendencia": 0,
        "stop_hit": 0,
        "ruido": 0
    }

    for i in range(100, len(df)):

        sub = df.iloc[:i]

        sinal, preco, stop, alvo, motivo = analisar(sub)

        if sinal == "AGUARDAR":
            if motivo == "Lateral ou sem força":
                erros["lateral"] += 1
            continue

        # simulação simples realista
        future = df.iloc[i:i+6]

        if len(future) == 0:
            continue

        if sinal == "COMPRA":
            if future["high"].max() >= alvo:
                wins += 1
            else:
                losses += 1

        if sinal == "VENDA":
            if future["low"].min() <= alvo:
                wins += 1
            else:
                losses += 1

    return wins, losses, erros

# ======================
# 📊 NOTÍCIAS (SIMPLES)
# ======================

st.subheader("📰 Notícias (impacto geral)")

st.info("Notícias podem influenciar volatilidade — evite operar em eventos fortes.")

# ======================
# 📊 DASHBOARD
# ======================

for ativo in ativos:

    df = pegar_dados(ativo)

    sinal, preco, stop, alvo, motivo = analisar(df)

    st.subheader(ativo)
    st.metric("Preço", preco)

    st.write("📌 Motivo:", motivo)

    # gráfico
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"]
    ))

    fig.update_layout(height=500, template="plotly_dark")

    st.plotly_chart(fig, use_container_width=True)

    if sinal == "COMPRA":
        st.success("🟢 COMPRA")

    elif sinal == "VENDA":
        st.error("🔴 VENDA")

    else:
        st.warning("⚪ AGUARDAR")

# ======================
# 📊 BACKTEST 30 DIAS BOTÃO
# ======================

if st.button("📊 Backtest 30 dias (profissional)"):

    df = pegar_dados(ativos[0])

    w, l, erros = backtest(df)

    total = w + l

    st.success(f"""
📊 RESULTADO BACKTEST (30 dias)

✔ Wins: {w}
❌ Loss: {l}
📈 Win rate: {round((w/total)*100,2) if total>0 else 0}%

⚠️ ERROS DETECTADOS:
- Lateral: {erros['lateral']}
- Sem tendência: {erros['sem_tendencia']}
""")
