import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from streamlit_autorefresh import st_autorefresh

# ======================
# CONFIG
# ======================

st.set_page_config(page_title="Sniper Pro AI", layout="wide")
st.title("📊 Sniper Pro AI - Profissional")

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

ATIVO = "EUR/USD"

st_autorefresh(interval=8000, key="refresh")

# ======================
# DADOS
# ======================

@st.cache_data(ttl=300)
def pegar_dados():

    df = td.time_series(
        symbol=ATIVO,
        interval="5min",
        outputsize=5000
    ).as_pandas()

    df = df[::-1].reset_index()

    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# ESTRATÉGIA PROFISSIONAL
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    preco = df["close"].iloc[-1]
    ema9 = df["EMA9"].iloc[-1]
    ema21 = df["EMA21"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    # ======================
    # 🔥 ESTRUTURA 12H
    # ======================

    ultimos = df.tail(144)

    suporte = ultimos["low"].min()
    resistencia = ultimos["high"].max()

    zona = preco * 0.0015

    perto_suporte = abs(preco - suporte) < zona
    perto_resistencia = abs(resistencia - preco) < zona

    # ======================
    # 📈 TENDÊNCIA
    # ======================

    tendencia_alta = ema9 > ema21
    tendencia_baixa = ema9 < ema21

    # ======================
    # 🚫 LATERALIDADE
    # ======================

    volatilidade = resistencia - suporte

    if volatilidade < preco * 0.002:
        return "AGUARDAR", preco, 0, 0, suporte, resistencia, "Mercado lateral"

    # ======================
    # 🟢 COMPRA
    # ======================

    if tendencia_alta and perto_suporte and rsi > 50:

        alvo = preco + (resistencia - preco) * 0.7
        stop = suporte

        return "COMPRA", preco, stop, alvo, suporte, resistencia, "Suporte + tendência"

    # ======================
    # 🔴 VENDA
    # ======================

    if tendencia_baixa and perto_resistencia and rsi < 50:

        alvo = preco - (preco - suporte) * 0.7
        stop = resistencia

        return "VENDA", preco, stop, alvo, suporte, resistencia, "Resistência + tendência"

    return "AGUARDAR", preco, 0, 0, suporte, resistencia, "Fora da zona"

# ======================
# BACKTEST 30 DIAS REAL
# ======================

def backtest(df):

    wins = 0
    losses = 0

    erros = {
        "lateral": 0,
        "fora_zona": 0,
        "stop": 0
    }

    df = df.copy()

    for i in range(200, len(df)-10):

        hora = df.loc[i, "datetime"].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, preco, stop, alvo, sup, res, motivo = analisar(sub)

        if sinal == "AGUARDAR":
            if motivo == "Mercado lateral":
                erros["lateral"] += 1
            else:
                erros["fora_zona"] += 1
            continue

        futuro = df.iloc[i:i+10]

        if sinal == "COMPRA":

            if futuro["high"].max() >= alvo:
                wins += 1
            elif futuro["low"].min() <= stop:
                losses += 1
                erros["stop"] += 1

        if sinal == "VENDA":

            if futuro["low"].min() <= alvo:
                wins += 1
            elif futuro["high"].max() >= stop:
                losses += 1
                erros["stop"] += 1

    return wins, losses, erros

# ======================
# DASHBOARD
# ======================

df = pegar_dados()

sinal, preco, stop, alvo, suporte, resistencia, motivo = analisar(df)

st.subheader(f"📊 {ATIVO}")

st.metric("Preço atual", round(preco, 5))

st.write("📌 Status:", motivo)

# ======================
# GRÁFICO
# ======================

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["datetime"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"]
))

# linhas suporte/resistência
fig.add_hline(y=suporte, line_dash="dot")
fig.add_hline(y=resistencia, line_dash="dot")

fig.update_layout(height=500, template="plotly_dark")

st.plotly_chart(fig, use_container_width=True)

# ======================
# SINAL
# ======================

if sinal == "COMPRA":
    st.success(f"🟢 COMPRA\nEntrada: {preco}\nStop: {stop}\nAlvo: {alvo}")

elif sinal == "VENDA":
    st.error(f"🔴 VENDA\nEntrada: {preco}\nStop: {stop}\nAlvo: {alvo}")

else:
    st.warning("⚪ AGUARDAR")

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest 30 dias (08h–12h)"):

    w, l, erros = backtest(df)

    total = w + l

    st.success(f"""
📊 RESULTADO

Wins: {w}
Loss: {l}
Winrate: {round((w/total)*100,2) if total>0 else 0}%

Erros:
- Lateral: {erros['lateral']}
- Fora da zona: {erros['fora_zona']}
- Stop atingido: {erros['stop']}
""")
