import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator, MACD
import datetime

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô apenas", layout="wide")
st.title("🤖 Robô apenas")

ATIVO = "EUR/USD"

if st.button("🔄 Atualizar dados"):
    st.rerun()

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados():
    df = td.time_series(
        symbol=ATIVO,
        interval="5min",
        outputsize=2000
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna().reset_index(drop=True)

# ======================
# TENDÊNCIA 1H
# ======================

def tendencia_1h(df):
    df["EMA50"] = EMAIndicator(df["close"], 50).ema_indicator()
    df["EMA200"] = EMAIndicator(df["close"], 200).ema_indicator()

    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        return "ALTA"
    elif df["EMA50"].iloc[-1] < df["EMA200"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# SUPORTE / RESISTÊNCIA
# ======================

def zonas(df):
    ult = df.tail(144)
    return ult["low"].min(), ult["high"].max()

# ======================
# VELA FORTE
# ======================

def vela_forte(df):
    c = df.iloc[-1]

    corpo = abs(c["close"] - c["open"])
    range_total = c["high"] - c["low"]

    if range_total == 0:
        return False

    return corpo / range_total > 0.6

# ======================
# PULLBACK
# ======================

def pullback(preco, sup, res):
    dist_sup = abs(preco - sup)
    dist_res = abs(preco - res)

    # perto de suporte OU resistência
    return min(dist_sup, dist_res) < (res - sup) * 0.25

# ======================
# MACD
# ======================

def get_macd(df):
    macd = MACD(df["close"])
    return macd.macd().iloc[-1]

# ======================
# ESTRATÉGIA (CORRIGIDA)
# ======================

def analisar(df):

    preco = df["close"].iloc[-1]
    sup, res = zonas(df)

    trend = tendencia_1h(df)
    macd = get_macd(df)

    erros = []

    # ======================
    # OBRIGATÓRIOS
    # ======================

    tem_pullback = pullback(preco, sup, res)
    tem_vela = vela_forte(df)

    if not tem_pullback:
        erros.append("Sem pullback")

    if not tem_vela:
        erros.append("Sem vela forte")

    # ❌ NÃO ENTRA SEM ISSO
    if not tem_pullback or not tem_vela:
        return "AGUARDAR", preco, None, None, erros

    # ======================
    # DIREÇÃO
    # ======================

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if trend == "ALTA" and macd > 0:
        return "COMPRA", preco, entrada, saida, erros

    if trend == "BAIXA" and macd < 0:
        return "VENDA", preco, entrada, saida, erros

    erros.append("Sem confirmação de tendência/MACD")
    return "AGUARDAR", preco, None, None, erros

# ======================
# BACKTEST
# ======================

def backtest(df):

    wins = 0
    loss = 0

    for i in range(200, len(df) - 1):

        sub = df.iloc[:i]

        sinal, _, _, _, _ = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entrada = df["close"].iloc[i]
        saida = df["close"].iloc[i + 1]

        if sinal == "COMPRA" and saida > entrada:
            wins += 1
        elif sinal == "VENDA" and saida < entrada:
            wins += 1
        else:
            loss += 1

    return wins, loss

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("Preço", preco)

st.write("Sinal:", sinal)

st.subheader("Motivos")

for e in erros:
    st.write("-", e)

# ======================
# BACKTEST
# ======================

if st.button("Backtest"):

    w, l = backtest(df)
    total = w + l

    st.write("Wins:", w)
    st.write("Loss:", l)
    st.write("Winrate:", (w / total * 100 if total else 0))

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

fig.update_layout(template="plotly_dark", height=500)

st.plotly_chart(fig, use_container_width=True)
