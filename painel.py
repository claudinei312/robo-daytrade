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

ATIVO = "USD/JPY"

# ======================
# BOTÃO ATUALIZAR
# ======================

if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

# ======================
# DADOS
# ======================

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
# TENDÊNCIA (M21)
# ======================

def tendencia(df):
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    if df["close"].iloc[-1] > df["EMA21"].iloc[-1]:
        return "ALTA"
    elif df["close"].iloc[-1] < df["EMA21"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# ESTRATÉGIA
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    preco = df["close"].iloc[-1]
    trend = tendencia(df)

    erros = []

    i = len(df) - 1

    # ======================
    # VELA FORTE
    # ======================

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        media = (
            abs(df["close"].iloc[i-1] - df["open"].iloc[i-1]) +
            abs(df["close"].iloc[i-2] - df["open"].iloc[i-2]) +
            abs(df["close"].iloc[i-3] - df["open"].iloc[i-3])
        ) / 3

        return corpo > media

    # ======================
    # TOQUE NA M21
    # ======================

    def tocou_m21(i):
        return df["low"].iloc[i] <= df["EMA21"].iloc[i] <= df["high"].iloc[i]

    # ======================
    # FILTRO LATERAL (IMPORTANTE)
    # ======================

    cruzamentos = 0

    for j in range(i-10, i):
        if (df["close"].iloc[j] > df["EMA21"].iloc[j] and df["close"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["close"].iloc[j] < df["EMA21"].iloc[j] and df["close"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    if cruzamentos >= 3:
        erros.append("Mercado lateral")
        agora = datetime.datetime.now()
        return "AGUARDAR", preco, agora, agora, erros

    # ======================
    # PULLBACK
    # ======================

    if trend == "ALTA":
        if tocou_m21(i):
            if df["close"].iloc[i] > df["open"].iloc[i] and vela_forte(i):
                entrada = df["datetime"].iloc[i] + datetime.timedelta(minutes=5)
                saida = entrada + datetime.timedelta(minutes=5)
                return "COMPRA", preco, entrada, saida, erros
            else:
                erros.append("Sem força na compra")

    if trend == "BAIXA":
        if tocou_m21(i):
            if df["close"].iloc[i] < df["open"].iloc[i] and vela_forte(i):
                entrada = df["datetime"].iloc[i] + datetime.timedelta(minutes=5)
                saida = entrada + datetime.timedelta(minutes=5)
                return "VENDA", preco, entrada, saida, erros
            else:
                erros.append("Sem força na venda")

    # ======================
    # CRUZAMENTO EMA5 x M21
    # ======================

    if i > 3:

        # COMPRA
        if df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1] and df["EMA5"].iloc[i] > df["EMA21"].iloc[i]:
            if df["close"].iloc[i] > df["open"].iloc[i] and vela_forte(i):
                entrada = df["datetime"].iloc[i] + datetime.timedelta(minutes=5)
                saida = entrada + datetime.timedelta(minutes=5)
                return "COMPRA", preco, entrada, saida, erros
            else:
                erros.append("Cruzamento sem força")

        # VENDA
        if df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1] and df["EMA5"].iloc[i] < df["EMA21"].iloc[i]:
            if df["close"].iloc[i] < df["open"].iloc[i] and vela_forte(i):
                entrada = df["datetime"].iloc[i] + datetime.timedelta(minutes=5)
                saida = entrada + datetime.timedelta(minutes=5)
                return "VENDA", preco, entrada, saida, erros
            else:
                erros.append("Cruzamento sem força")

    erros.append("Sem entrada válida")

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada +
