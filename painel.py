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

st.set_page_config(page_title="Robô M1 Scanner", layout="wide")
st.title("📊 Robô EMA Cross M1 + Backtest")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS M1
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="1min",   # 🔥 M1
        outputsize=5000
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# BACKTEST M1
# ======================

def backtest(df, ativo):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    wins = 0
    loss = 0

    trades = []

    # 🔥 M1 precisa SL menor
    SL = 0.0003
    TP = 0.0005

    for i in range(50, len(df) - 10):

        hora = df["datetime"].iloc[i].hour

        # 📌 filtro horário (08-17)
        if not (8 <= hora <= 17):
            continue

        prev = i - 1

        cross_up = (
            df["EMA5"].iloc[prev] < df["EMA21"].iloc[prev] and
            df["EMA5"].iloc[i] > df["EMA21"].iloc[i]
        )

        cross_down = (
            df["EMA5"].iloc[prev] > df["EMA21"].iloc[prev] and
            df["EMA5"].iloc[i] < df["EMA21"].iloc[i]
        )

        if not cross_up and not cross_down:
            continue

        entry = df["close"].iloc[i]
        direction = "COMPRA" if cross_up else "VENDA"

        result = None

        # ======================
        # SIMULAÇÃO REAL M1
        # ======================

        for j in range(i+1, i+20):

            high = df["high"].iloc[j]
            low = df["low"].iloc[j]

            # COMPRA
            if direction == "COMPRA":

                if low <= entry * (1 - SL):
                    result = "LOSS"
                    break

                if high >= entry * (1 + TP):
                    result = "WIN"
                    break

            # VENDA
            if direction == "VENDA":

                if high >= entry * (1 + SL):
                    result = "LOSS"
                    break

                if low <= entry * (1 - TP):
                    result = "WIN"
                    break

        if result is None:
            continue

        if result == "WIN":
            wins += 1
        else:
            loss += 1

        trades.append({
            "ativo": ativo,
            "tipo": direction,
            "entrada": entry,
            "resultado": result,
            "hora": df["datetime"].iloc[i]
        })

    return wins, loss, trades

# ======================
# EXECUÇÃO
# ======================

if st.button("📊 Rodar Backtest M1 (Ontem 08-17)"):

    resultados = []

    for ativo in ATIVOS:

        df = pegar_dados(ativo)

        w, l, trades = backtest(df, ativo)

        total = w + l
        acc = (w / total * 100) if total > 0 else 0

        resultados.append({
            "ativo": ativo,
            "wins": w,
            "loss": l,
            "acc": acc,
            "trades": trades
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

    w, l, trades = backtest(pegar_dados(melhor["ativo"]), melhor["ativo"])

    st.subheader("📈 RESULTADO FINAL")

    st.write("Wins:", w)
    st.write("Loss:", l)
    st.write("Assertividade:", round((w/(w+l))*100 if (w+l)>0 else 0,2))

    # ======================
    # TRADES
    # ======================

    st.subheader("📜 TRADES DETALHADOS")

    for t in trades[-30:]:
        st.write(t)

# ======================
# GRÁFICO (CORRIGIDO M1)
# ======================

ativo_grafico = st.selectbox("📊 Escolha o ativo do gráfico", ATIVOS)

df = pegar_dados(ativo_grafico)

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
