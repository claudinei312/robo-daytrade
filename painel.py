import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Backtest Real SL/TP", layout="wide")
st.title("📊 EMA Cross + Stop Loss / Take Profit REAL")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=1500
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# EMA CROSS
# ======================

def vela_forte(df, i):
    corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
    rng = df["high"].iloc[i] - df["low"].iloc[i]
    if rng == 0:
        return False
    return (corpo / rng) >= 0.5

# ======================
# BACKTEST REAL SL/TP
# ======================

def backtest_real(df):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    wins = 0
    loss = 0
    trades = []

    SL_PCT = 0.0008   # 0.08%
    TP_PCT = 0.0012   # 0.12%
    MAX_BARS = 6      # 30 minutos

    for i in range(50, len(df) - MAX_BARS):

        cruz_compra = (
            df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]
        )

        cruz_venda = (
            df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]
        )

        if not (cruz_compra or cruz_venda):
            continue

        entry_price = df["close"].iloc[i]

        if cruz_compra:
            direction = "BUY"
            sl = entry_price * (1 - SL_PCT)
            tp = entry_price * (1 + TP_PCT)

        else:
            direction = "SELL"
            sl = entry_price * (1 + SL_PCT)
            tp = entry_price * (1 - TP_PCT)

        result = None
        exit_price = None

        # ======================
        # MONITORAMENTO REAL
        # ======================

        for j in range(i+1, i+MAX_BARS):

            high = df["high"].iloc[j]
            low = df["low"].iloc[j]

            if direction == "BUY":

                if low <= sl:
                    result = "LOSS"
                    exit_price = sl
                    break

                if high >= tp:
                    result = "WIN"
                    exit_price = tp
                    break

            if direction == "SELL":

                if high >= sl:
                    result = "LOSS"
                    exit_price = sl
                    break

                if low <= tp:
                    result = "WIN"
                    exit_price = tp
                    break

        if result is None:
            continue

        if result == "WIN":
            wins += 1
        else:
            loss += 1

        trades.append({
            "tipo": direction,
            "entrada": entry_price,
            "saida": exit_price,
            "resultado": result,
            "data": df["datetime"].iloc[i]
        })

    return wins, loss, trades

# ======================
# EXECUÇÃO POR ATIVO
# ======================

resultados = []

for ativo in ATIVOS:

    df = pegar_dados(ativo)

    w, l, trades = backtest_real(df)

    total = w + l
    acc = (w / total * 100) if total > 0 else 0

    resultados.append({
        "ativo": ativo,
        "wins": w,
        "loss": l,
        "acc": acc,
        "trades": trades,
        "df": df
    })

melhor = max(resultados, key=lambda x: x["acc"])

# ======================
# PAINEL
# ======================

st.subheader("📊 Ranking de Ativos (REAL SL/TP)")

for r in resultados:
    st.write(f"""
### {r['ativo']}
Wins: {r['wins']} | Loss: {r['loss']} | Assertividade: {round(r['acc'],2)}%
""")

st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

# ======================
# RESULTADO
# ======================

w, l, trades = backtest_real(melhor["df"])

acc = (w / (w + l) * 100) if (w + l) > 0 else 0

st.subheader("📈 RESULTADO FINAL")

st.write("Wins:", w)
st.write("Loss:", l)
st.write("Assertividade:", round(acc,2))

# ======================
# TRADES
# ======================

st.subheader("📜 TRADES REAIS")

for t in trades[-20:]:
    st.write(t)

# ======================
# GRÁFICO
# ======================

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=melhor["df"]["datetime"],
    open=melhor["df"]["open"],
    high=melhor["df"]["high"],
    low=melhor["df"]["low"],
    close=melhor["df"]["close"]
))

fig.update_layout(template="plotly_dark", height=600)

st.plotly_chart(fig, use_container_width=True)
