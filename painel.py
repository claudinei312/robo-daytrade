import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
import datetime

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô tendência forte", layout="wide")
st.title("🤖 Robô Trend Filter FIX")

ATIVO = "USD/JPY"

@st.cache_data(ttl=120)
def pegar_dados():
    df = td.time_series(
        symbol=ATIVO,
        interval="5min",
        outputsize=5000
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# TENDÊNCIA MAIS REALISTA
# ======================

def tendencia_forte(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    i = len(df) - 1

    inclinacao = (df["EMA21"].iloc[i] - df["EMA21"].iloc[i-5])

    cruzamentos = 0
    for j in range(i-10, i):
        if j <= 0:
            continue

        if (df["EMA5"].iloc[j] > df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["EMA5"].iloc[j] < df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    # 🔥 AJUSTE IMPORTANTE (mais realista pro JPY)
    if cruzamentos >= 5:
        return False, "LATERAL"

    if abs(inclinacao) < 0.0008:
        return False, "SEM TENDÊNCIA"

    return True, "FORTE"


# ======================
# ESTRATÉGIA
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    preco = df["close"].iloc[-1]
    erros = []

    i = len(df) - 1

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        range_total = df["high"].iloc[i] - df["low"].iloc[i]
        if range_total == 0:
            return False
        return (corpo / range_total) > 0.55  # mais flexível

    ok, status = tendencia_forte(df)

    if not ok:
        erros.append(status)
        agora = datetime.datetime.now()
        return "AGUARDAR", preco, agora, agora, erros

    # ======================
    # CRUZAMENTO MAIS JUSTO
    # ======================

    if i < 3:
        return "AGUARDAR", preco, None, None, ["sem dados"]

    # COMPRA
    if df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1] and df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2]:

        if df["EMA21"].iloc[i] > df["EMA21"].iloc[i-1]:

            if vela_forte(i-1):

                if df["high"].iloc[i] > df["high"].iloc[i-1]:

                    entrada = df["datetime"].iloc[i]
                    saida = entrada + datetime.timedelta(minutes=5)
                    return "COMPRA", preco, entrada, saida, erros

    # VENDA
    if df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1] and df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2]:

        if df["EMA21"].iloc[i] < df["EMA21"].iloc[i-1]:

            if vela_forte(i-1):

                if df["low"].iloc[i] < df["low"].iloc[i-1]:

                    entrada = df["datetime"].iloc[i]
                    saida = entrada + datetime.timedelta(minutes=5)
                    return "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, None, None, ["sem setup"]


# ======================
# BACKTEST
# ======================

def backtest(df):

    wins = 0
    loss = 0
    log = []

    for i in range(60, len(df)-2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 17:
            continue

        sub = df.iloc[:i].copy()

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entrada = df["close"].iloc[i+1]
        saida = df["close"].iloc[i+2]

        trade = {
            "data": str(df["datetime"].iloc[i]),
            "tipo": sinal,
            "entrada": entrada,
            "saida": saida,
            "erros": erros
        }

        if sinal == "COMPRA":
            if saida > entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"

        if sinal == "VENDA":
            if saida < entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"

        log.append(trade)

    return wins, loss, log


df = pegar_dados()

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("Preço", preco)

st.write("Sinal:", sinal)
st.write("Erros:", erros)

if st.button("Backtest"):

    wins, loss, log = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.write("Wins:", wins)
    st.write("Loss:", loss)
    st.write("Assertividade:", round(taxa, 2))

    st.subheader("LOG")

    for t in log:
        st.write(t)


fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["datetime"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"]
))

st.plotly_chart(fig)
