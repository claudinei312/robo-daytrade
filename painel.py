import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
import datetime

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="EMA Cross Scanner", layout="wide")
st.title("📊 EMA Cross M5 Scanner + Backtest")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
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
# BACKTEST REAL
# ======================

def backtest(df):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    wins = 0
    loss = 0

    trades = []
    erros = {
        "cruzamentos": 0,
        "wins_compra": 0,
        "wins_venda": 0,
        "loss_compra": 0,
        "loss_venda": 0
    }

    SL = 0.0008
    TP = 0.0012

    for i in range(50, len(df) - 10):

        hora = df["datetime"].iloc[i].hour

        # janela operacional (Brasil + Londres)
        if not (8 <= hora <= 11 or 13 <= hora <= 15):
            continue

        prev = i - 1

        cross_up = df["EMA5"].iloc[prev] < df["EMA21"].iloc[prev] and df["EMA5"].iloc[i] > df["EMA21"].iloc[i]
        cross_down = df["EMA5"].iloc[prev] > df["EMA21"].iloc[prev] and df["EMA5"].iloc[i] < df["EMA21"].iloc[i]

        if not cross_up and not cross_down:
            continue

        entry = df["close"].iloc[i+1]
        direction = None

        if cross_up:
            direction = "COMPRA"
        elif cross_down:
            direction = "VENDA"

        result = None

        # ======================
        # SIMULAÇÃO REAL
        # ======================

        for j in range(i+2, i+12):

            high = df["high"].iloc[j]
            low = df["low"].iloc[j]

            if direction == "COMPRA":

                if low <= entry * (1 - SL):
                    result = "LOSS"
                    erros["loss_compra"] += 1
                    break

                if high >= entry * (1 + TP):
                    result = "WIN"
                    erros["wins_compra"] += 1
                    break

            if direction == "VENDA":

                if high >= entry * (1 + SL):
                    result = "LOSS"
                    erros["loss_venda"] += 1
                    break

                if low <= entry * (1 - TP):
                    result = "WIN"
                    erros["wins_venda"] += 1
                    break

        if result is None:
            continue

        if result == "WIN":
            wins += 1
        else:
            loss += 1

        trades.append({
            "ativo": "ATIVO",
            "tipo": direction,
            "entrada": entry,
            "resultado": result,
            "hora": df["datetime"].iloc[i]
        })

    return wins, loss, trades, erros

# ======================
# EXECUÇÃO
# ======================

if st.button("📊 Rodar Backtest Completo"):

    resultados = []

    for ativo in ATIVOS:

        df = pegar_dados(ativo)

        w, l, trades, erros = backtest(df)

        total = w + l
        acc = (w / total * 100) if total > 0 else 0

        resultados.append({
            "ativo": ativo,
            "wins": w,
            "loss": l,
            "acc": acc,
            "trades": trades,
            "erros": erros,
            "df": df
        })

    melhor = max(resultados, key=lambda x: x["acc"])

    # ======================
    # RANKING
    # ======================

    st.subheader("📊 Ranking de Ativos")

    for r in resultados:
        st.write(f"""
### {r['ativo']}
Wins: {r['wins']} | Loss: {r['loss']} | Assertividade: {round(r['acc'],2)}%
""")

    st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

    # ======================
    # RESULTADO FINAL
    # ======================

    w, l, trades, erros = backtest(melhor["df"])

    st.subheader("📈 RESULTADO FINAL")

    st.write("Wins:", w)
    st.write("Loss:", l)
    st.write("Assertividade:", round((w/(w+l))*100 if (w+l)>0 else 0,2))

    # ======================
    # DETALHES
    # ======================

    st.subheader("📜 TRADES DETALHADOS")

    for t in trades[-30:]:
        st.write(t)

    st.subheader("⚠️ ESTATÍSTICAS DE ERRO")

    st.write(erros)

# ======================
# GRÁFICO
# ======================

df = pegar_dados("USD/JPY")

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["datetime"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"]
))

fig.update_layout(template="plotly_dark", height=500)

st.plotly_chart(fig, use_container_width=True)
