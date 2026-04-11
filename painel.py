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

st.set_page_config(page_title="Hedge Bot EMA Pro FINAL", layout="wide")
st.title("💎 Robô Profissional EMA Cross FINAL")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="1min",
        outputsize=5000
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# VELA FORTE
# ======================

def vela_forte(df, i):
    corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
    range_total = df["high"].iloc[i] - df["low"].iloc[i]
    if range_total == 0:
        return False
    return (corpo / range_total) > 0.6

# ======================
# VOLATILIDADE (ATR SIMPLIFICADO)
# ======================

def volatilidade(df, i):
    return (df["high"].iloc[i] - df["low"].iloc[i])

# ======================
# BACKTEST FINAL
# ======================

def backtest(df, ativo):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["EMA200"] = EMAIndicator(df["close"], 200).ema_indicator()

    wins = 0
    loss = 0
    trades = []

    erros = {
        "baixa_tendencia": 0,
        "sem_forca": 0,
        "lateral": 0,
        "volatilidade_baixa": 0
    }

    for i in range(250, len(df) - 20):

        hora = df["datetime"].iloc[i].hour

        if not (8 <= hora <= 17):
            continue

        price = df["close"].iloc[i]

        # ======================
        # TENDÊNCIA
        # ======================

        trend_up = price > df["EMA200"].iloc[i]
        trend_down = price < df["EMA200"].iloc[i]

        # ======================
        # LATERALIDADE
        # ======================

        cruz = 0
        for j in range(i-10, i):
            if (df["EMA5"].iloc[j] > df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
               (df["EMA5"].iloc[j] < df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] > df["EMA21"].iloc[j-1]):
                cruz += 1

        if cruz >= 5:
            erros["lateral"] += 1
            continue

        # ======================
        # CRUZAMENTO
        # ======================

        cross_up = df["EMA5"].iloc[i-3] < df["EMA21"].iloc[i-3] and df["EMA5"].iloc[i] > df["EMA21"].iloc[i]
        cross_down = df["EMA5"].iloc[i-3] > df["EMA21"].iloc[i-3] and df["EMA5"].iloc[i] < df["EMA21"].iloc[i]

        if not cross_up and not cross_down:
            continue

        direction = None

        # ======================
        # FILTROS DE QUALIDADE
        # ======================

        vol = volatilidade(df, i)

        SL = max(vol * 0.8, 0.0003)
        TP = SL * 1.5

        # ======================
        # COMPRA
        # ======================

        if cross_up:

            if not trend_up:
                erros["baixa_tendencia"] += 1
                continue

            if not vela_forte(df, i):
                erros["sem_forca"] += 1
                continue

            direction = "COMPRA"

        # ======================
        # VENDA
        # ======================

        if cross_down:

            if not trend_down:
                erros["baixa_tendencia"] += 1
                continue

            if not vela_forte(df, i):
                erros["sem_forca"] += 1
                continue

            direction = "VENDA"

        if direction is None:
            continue

        entry = price
        result = None

        # ======================
        # EXECUÇÃO REAL
        # ======================

        for j in range(i+1, i+20):

            high = df["high"].iloc[j]
            low = df["low"].iloc[j]

            if direction == "COMPRA":

                if low <= entry - SL:
                    result = "LOSS"
                    break

                if high >= entry + TP:
                    result = "WIN"
                    break

            if direction == "VENDA":

                if high >= entry + SL:
                    result = "LOSS"
                    break

                if low <= entry - TP:
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

    return wins, loss, trades, erros

# ======================
# EXECUÇÃO
# ======================

if st.button("🚀 RODAR ROBÔ FINAL PRO"):

    resultados = []

    for ativo in ATIVOS:

        df = pegar_dados(ativo)

        w, l, trades, erros = backtest(df, ativo)

        total = w + l
        acc = (w / total * 100) if total > 0 else 0

        resultados.append({
            "ativo": ativo,
            "wins": w,
            "loss": l,
            "acc": acc,
            "trades": trades,
            "erros": erros
        })

    melhor = max(resultados, key=lambda x: x["acc"])

    st.subheader("📊 Ranking de Ativos")

    for r in resultados:
        st.write(f"""
### {r['ativo']}
Wins: {r['wins']} | Loss: {r['loss']} | Assertividade: {round(r['acc'],2)}%
""")

    st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

    st.subheader("📈 Resultado Final")

    st.write("Wins:", melhor["wins"])
    st.write("Loss:", melhor["loss"])
    st.write("Assertividade:", round(melhor["acc"], 2))

    st.subheader("📉 Motivos de rejeição")

    st.json(melhor["erros"])

    st.subheader("📜 Trades")

    for t in melhor["trades"][-20:]:
        st.write(t)

# ======================
# GRÁFICO
# ======================

ativo_grafico = st.selectbox("📊 Ativo", ATIVOS)

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
