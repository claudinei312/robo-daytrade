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

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 ESTRATÉGIA (OTIMIZADA)
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

    # 🔥 tendência forte real
    tendencia_forte = abs(ema9 - ema21) > (preco * 0.001)

    alta = ema9 > ema21
    baixa = ema9 < ema21

    # 🕯 candle forte
    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]
    candle_ok = body > rng * 0.65

    # 📉 RSI filtro
    rsi_buy_ok = rsi < 65
    rsi_sell_ok = rsi > 35

    # ❌ filtro lateral
    if not tendencia_forte or not candle_ok:
        return "AGUARDAR", preco, 0, 0, "Lateral / sem força"

    # 🟢 COMPRA
    if alta and preco <= suporte * 1.002 and rsi_buy_ok:
        alvo = preco + (preco - suporte) * 2
        stop = suporte
        return "COMPRA", preco, stop, alvo, "Pullback tendência alta"

    # 🔴 VENDA
    if baixa and preco >= resistencia * 0.998 and rsi_sell_ok:
        alvo = preco - (resistencia - preco) * 2
        stop = resistencia
        return "VENDA", preco, stop, alvo, "Rejeição resistência"

    return "AGUARDAR", preco, 0, 0, "Sem setup"

# ======================
# 📊 BACKTEST 30 DIAS (CORRIGIDO)
# ======================

def backtest(df):

    df = df.copy()

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    df = df.dropna().reset_index(drop=True)

    wins = 0
    losses = 0

    erros = {
        "lateral": 0,
        "sem_tendencia": 0,
        "entrada_ruim": 0
    }

    in_trade = False
    direction = None
    target = 0
    stop = 0

    for i in range(100, len(df)):

        hora = df.loc[i, "datetime"].hour

        # 🎯 FILTRO 8h–12h
        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, preco, stop_calc, alvo, motivo = analisar(sub)

        # ======================
        # 🔴 GERENCIAMENTO
        # ======================

        if in_trade:

            high = df.loc[i, "high"]
            low = df.loc[i, "low"]

            if direction == "COMPRA":

                if high >= target:
                    wins += 1
                    in_trade = False
                    continue

                if low <= stop:
                    losses += 1
                    in_trade = False
                    continue

            if direction == "VENDA":

                if low <= target:
                    wins += 1
                    in_trade = False
                    continue

                if high >= stop:
                    losses += 1
                    in_trade = False
                    continue

        # ======================
        # 🟡 ENTRADA
        # ======================

        if not in_trade:

            if sinal == "AGUARDAR":

                if motivo == "Lateral / sem força":
                    erros["lateral"] += 1
                else:
                    erros["sem_tendencia"] += 1

                continue

            in_trade = True
            direction = sinal
            target = alvo
            stop = stop_calc

    return wins, losses, erros

# ======================
# 📊 DASHBOARD
# ======================

for ativo in ativos:

    df = pegar_dados(ativo)

    sinal, preco, stop, alvo, motivo = analisar(df)

    st.subheader(f"📊 {ativo}")

    st.metric("Preço atual", preco)

    st.write("📌 Status:", motivo)

    # ======================
    # 📈 GRÁFICO
    # ======================

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

    # ======================
    # 📊 SINAL
    # ======================

    if sinal == "COMPRA":
        st.success("🟢 COMPRA")

    elif sinal == "VENDA":
        st.error("🔴 VENDA")

    else:
        st.warning("⚪ AGUARDAR")

# ======================
# 📊 BACKTEST BOTÃO
# ======================

if st.button("📊 Rodar Backtest 30 dias (8h–12h)"):

    df = pegar_dados(ativos[0])

    w, l, erros = backtest(df)

    total = w + l

    st.success(f"""
📊 RESULTADO BACKTEST 30 DIAS

✔ Wins: {w}
❌ Loss: {l}
📈 Win Rate: {round((w/total)*100,2) if total>0 else 0}%

📉 ERROS:
- Lateral: {erros['lateral']}
- Sem tendência: {erros['sem_tendencia']}
""")
