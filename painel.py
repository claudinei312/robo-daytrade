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

st.set_page_config(page_title="Robô apenas", layout="wide")
st.title("🤖 Robô apenas")

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
# BACKTEST REAL (SEM DEPENDER DA FUNÇÃO ANALISAR)
# ======================

def backtest(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    wins = 0
    loss = 0

    erros_log = []
    trades = []

    # estatísticas de erro
    stats = {
        "sem_setup": 0,
        "forca": 0,
        "cruzamento": 0,
        "lateral": 0,
        "rompimento": 0
    }

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        rng = df["high"].iloc[i] - df["low"].iloc[i]
        if rng == 0:
            return False
        return (corpo / rng) > 0.6

    for i in range(50, len(df)-10):

        hora = df["datetime"].iloc[i].hour
        if not (8 <= hora <= 11 or 13 <= hora <= 15):
            continue

        cruz_compra = (
            df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]
        )

        cruz_venda = (
            df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]
        )

        if not cruz_compra and not cruz_venda:
            stats["sem_setup"] += 1
            continue

        entry = df["close"].iloc[i]

        SL = 0.0008
        TP = 0.0012

        result = None
        tipo = None

        # ======================
        # COMPRA
        # ======================

        if cruz_compra:

            tipo = "COMPRA"

            if not vela_forte(i-1):
                stats["forca"] += 1
                continue

            for j in range(i+1, i+8):

                if df["low"].iloc[j] <= entry * (1 - SL):
                    result = "LOSS"
                    break

                if df["high"].iloc[j] >= entry * (1 + TP):
                    result = "WIN"
                    break

        # ======================
        # VENDA
        # ======================

        if cruz_venda:

            tipo = "VENDA"

            if not vela_forte(i-1):
                stats["forca"] += 1
                continue

            for j in range(i+1, i+8):

                if df["high"].iloc[j] >= entry * (1 + SL):
                    result = "LOSS"
                    break

                if df["low"].iloc[j] <= entry * (1 - TP):
                    result = "WIN"
                    break

        if result is None:
            continue

        if result == "WIN":
            wins += 1
        else:
            loss += 1

        trades.append({
            "ativo": "USD/JPY",
            "tipo": tipo,
            "entrada": entry,
            "resultado": result,
            "hora": df["datetime"].iloc[i]
        })

    return wins, loss, trades, stats

# ======================
# EXECUÇÃO MULTI-ATIVO
# ======================

if st.button("📊 Rodar Backtest Completo"):

    resultados = []

    for ativo in ATIVOS:

        df = pegar_dados(ativo)

        w, l, trades, stats = backtest(df)

        total = w + l
        acc = (w / total * 100) if total > 0 else 0

        resultados.append({
            "ativo": ativo,
            "wins": w,
            "loss": l,
            "acc": acc,
            "trades": trades,
            "stats": stats,
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

Erros:
- sem_setup: {r['stats']['sem_setup']}
- força: {r['stats']['forca']}
""")

    st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

    # ======================
    # RESULTADO FINAL
    # ======================

    w, l, trades, stats = backtest(melhor["df"])

    st.subheader("📈 RESULTADO FINAL")

    st.write("Wins:", w)
    st.write("Loss:", l)
    st.write("Assertividade:", round((w/(w+l))*100 if (w+l)>0 else 0,2))

    # ======================
    # TRADES DETALHADOS
    # ======================

    st.subheader("📜 TRADES DETALHADOS")

    for t in trades[-30:]:
        st.write(t)

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

st.plotly_chart(fig, use_container_width=True)
