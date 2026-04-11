import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô Filtrado PRO", layout="wide")
st.title("📊 EMA Cross + Filtro de Força + Tendência")

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
# TENDÊNCIA
# ======================

def tendencia(df):

    ema21 = EMAIndicator(df["close"], 21).ema_indicator()

    if df["close"].iloc[-1] > ema21.iloc[-1]:
        return "ALTA"
    elif df["close"].iloc[-1] < ema21.iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# FORÇA DE MERCADO (ATR)
# ======================

def mercado_forte(df):

    atr = AverageTrueRange(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    ).average_true_range()

    # força mínima baseada no preço
    return atr.iloc[-1] > (df["close"].iloc[-1] * 0.0005)

# ======================
# BACKTEST
# ======================

def backtest(df):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    wins = 0
    loss = 0
    trades = []

    for i in range(60, len(df) - 3):

        # ======================
        # FILTRO DE MERCADO
        # ======================

        if not mercado_forte(df):
            continue

        trend = tendencia(df)

        if trend == "LATERAL":
            continue

        # ======================
        # CRUZAMENTO
        # ======================

        cruz_compra = (
            df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]
        )

        cruz_venda = (
            df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]
        )

        entry = df["close"].iloc[i]
        sl = 0.0008
        tp = 0.0012

        # ======================
        # COMPRA
        # ======================

        if cruz_compra:

            result = None

            for j in range(i+1, i+6):

                if df["low"].iloc[j] <= entry * (1 - sl):
                    result = "LOSS"
                    break

                if df["high"].iloc[j] >= entry * (1 + tp):
                    result = "WIN"
                    break

            if result == "WIN":
                wins += 1
            elif result == "LOSS":
                loss += 1
            else:
                continue

            trades.append({
                "tipo": "COMPRA",
                "resultado": result
            })

        # ======================
        # VENDA
        # ======================

        if cruz_venda:

            result = None

            for j in range(i+1, i+6):

                if df["high"].iloc[j] >= entry * (1 + sl):
                    result = "LOSS"
                    break

                if df["low"].iloc[j] <= entry * (1 - tp):
                    result = "WIN"
                    break

            if result == "WIN":
                wins += 1
            elif result == "LOSS":
                loss += 1
            else:
                continue

            trades.append({
                "tipo": "VENDA",
                "resultado": result
            })

    return wins, loss, trades

# ======================
# EXECUÇÃO
# ======================

resultados = []

for ativo in ATIVOS:

    df = pegar_dados(ativo)

    w, l, trades = backtest(df)

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

st.subheader("📊 Ranking de Ativos (FILTRADO)")

for r in resultados:
    st.write(f"""
### {r['ativo']}
Wins: {r['wins']} | Loss: {r['loss']} | Assertividade: {round(r['acc'],2)}%
""")

st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

w, l, trades = backtest(melhor["df"])

acc = (w / (w + l) * 100) if (w + l) > 0 else 0

st.subheader("📈 RESULTADO FINAL")

st.write("Wins:", w)
st.write("Loss:", l)
st.write("Assertividade:", round(acc,2))

st.subheader("📜 TRADES")

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
