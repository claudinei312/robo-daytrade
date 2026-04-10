import streamlit as st
from twelvedata import TDClient
import pandas as pd
import datetime
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator

# ======================
# 🎨 CONFIGURAÇÃO
# ======================

st.set_page_config(page_title="Sniper Pro Trading", layout="wide")

st.title("📊 Sniper Pro Trading System")

# ======================
# 🔐 API (SUA API INSERIDA)
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"

td = TDClient(apikey=API_KEY)

ativos = ["USD/JPY:FX"]

st_autorefresh(interval=5000, key="refresh")

# ======================
# 📥 DADOS
# ======================

@st.cache_data(ttl=240)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=500
    ).as_pandas()

    df = df[::-1].reset_index()

    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 ESTRATÉGIA (MELHORADA)
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

    # tendência
    tendencia = abs(ma9 - ma21) > 0.00025

    # candle forte
    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]
    candle = body > rng * 0.6

    # volatilidade
    vol = df["high"].rolling(10).max().iloc[-1] - df["low"].rolling(10).min().iloc[-1]
    vol_ok = vol > preco * 0.0005

    if not tendencia or not candle or not vol_ok:
        return "AGUARDAR", preco, 0, 0

    # 🟢 COMPRA
    if ma9 > ma21 and preco <= suporte * 1.001 and rsi < 70:
        return "COMPRA", preco, suporte, preco + (preco - suporte) * 2

    # 🔴 VENDA
    if ma9 < ma21 and preco >= resistencia * 0.999 and rsi > 30:
        return "VENDA", preco, resistencia, preco - (resistencia - preco) * 2

    return "AGUARDAR", preco, 0, 0

# ======================
# 📊 BACKTEST (15 DIAS / 8H–12H)
# ======================

def backtest(df):

    df["MA9"] = SMAIndicator(df["close"], 9).sma_indicator()
    df["MA21"] = SMAIndicator(df["close"], 21).sma_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    df = df.dropna()

    wins = 0
    losses = 0

    for i in range(50, len(df)):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, preco, stop, alvo = analisar(sub)

        if sinal == "COMPRA":
            if df["high"].iloc[i] >= alvo:
                wins += 1
            else:
                losses += 1

        if sinal == "VENDA":
            if df["low"].iloc[i] <= alvo:
                wins += 1
            else:
                losses += 1

    return wins, losses

# ======================
# 📊 DASHBOARD
# ======================

for ativo in ativos:

    df = pegar_dados(ativo)

    sinal, preco, stop, alvo = analisar(df)

    st.subheader(f"📊 {ativo}")

    st.metric("Preço atual", preco)

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

if st.button("📊 Rodar Backtest (8h–12h / 15 dias)"):

    df = pegar_dados(ativos[0])
    w, l = backtest(df)

    st.success(f"""
📊 RESULTADO BACKTEST

✔ Wins: {w}
❌ Loss: {l}
📈 Win rate: {round((w/(w+l))*100, 2) if (w+l)>0 else 0}%
""")
