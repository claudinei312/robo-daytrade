import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
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
        outputsize=5000
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
    df["EMA50"] = EMAIndicator(df["close"],50).ema_indicator()
    df["EMA200"] = EMAIndicator(df["close"],200).ema_indicator()

    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        return "ALTA"
    elif df["EMA50"].iloc[-1] < df["EMA200"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# ZONAS (12H)
# ======================

def zonas(df):
    ult = df.tail(144)
    return ult["low"].min(), ult["high"].max()

# ======================
# DETECTAR 2 TOQUES (SUPORTE REAL)
# ======================

def suporte_forte(df, suporte):

    toques = 0

    for i in range(len(df)-20, len(df)):
        if abs(df["low"].iloc[i] - suporte) < (suporte * 0.001):
            toques += 1

    return toques >= 2

# ======================
# CANDLE DE REJEIÇÃO (PRICE ACTION)
# ======================

def rejeicao_candle(candle):

    corpo = abs(candle["close"] - candle["open"])
    pavio_baixo = candle["open"] - candle["low"]

    return pavio_baixo > corpo * 1.5

# ======================
# ESTRATÉGIA PROFISSIONAL
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"],9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"],14).rsi()

    macd = MACD(df["close"])
    df["macd"] = macd.macd()

    preco = df["close"].iloc[-1]

    sup, res = zonas(df)
    trend = tendencia(df)

    score = 0
    erros = []

    # ======================
    # CONTEXTO
    # ======================
    if trend == "ALTA":
        score += 1
    elif trend == "BAIXA":
        score -= 1
    else:
        erros.append("Mercado lateral")

    # ======================
    # EMA
    # ======================
    if df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        score += 1
    else:
        erros.append("EMA contra")

    # ======================
    # RSI MELHORADO (ÚNICA ALTERAÇÃO)
    # ======================
    rsi_atual = df["RSI"].iloc[-1]
    rsi_anterior = df["RSI"].iloc[-2]

    if rsi_atual > 60 and rsi_atual > rsi_anterior:
        score += 1

    elif rsi_anterior < 30 and rsi_atual > 30:
        score += 1

    elif rsi_atual < 40 and rsi_atual < rsi_anterior:
        score -= 1

    elif rsi_anterior > 70 and rsi_atual < 70:
        score -= 1

    else:
        erros.append("RSI neutro ou fraco")

    # ======================
    # MACD
    # ======================
    if df["macd"].iloc[-1] > 0:
        score += 1
    else:
        erros.append("MACD contra")

    # ======================
    # SUPORTE PROFISSIONAL
    # ======================
    candle = df.iloc[-1]

    perto = abs(preco - sup) < (res - sup)*0.15
    toque_duplo = suporte_forte(df, sup)
    rejeicao = rejeicao_candle(candle)

    if perto and toque_duplo and rejeicao:
        score += 2
    else:
        if not perto:
            erros.append("Longe do suporte")
        if not toque_duplo:
            erros.append("Sem 2 toques no suporte")
        if not rejeicao:
            erros.append("Sem rejeição do candle")

    # ======================
    # DECISÃO
    # ======================
    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if score >= 5:
        return "COMPRA", preco, entrada, saida, erros

    if score <= -4:
        return "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST INTELIGENTE
# ======================

def backtest(df):

    wins = 0
    loss = 0
    erros_log = []

    for i in range(200, len(df)-1):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entrada = df["close"].iloc[i]
        saida = df["close"].iloc[i+1]

        if sinal == "COMPRA":
            if saida > entrada:
                wins += 1
            else:
                loss += 1
                erros_log.extend(erros)

        if sinal == "VENDA":
            if saida < entrada:
                wins += 1
            else:
                loss += 1
                erros_log.extend(erros)

    return wins, loss, erros_log

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

trend = tendencia(df)
st.write("📊 Tendência:", trend)

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("💰 Preço atual", preco)

if sinal == "COMPRA":
    st.success(f"🟢 COMPRA\nEntrada: {entrada.strftime('%H:%M')} | Saída: {saida.strftime('%H:%M')}")
elif sinal == "VENDA":
    st.error(f"🔴 VENDA\nEntrada: {entrada.strftime('%H:%M')} | Saída: {saida.strftime('%H:%M')}")
else:
    st.warning("⚪ AGUARDAR")

st.subheader("⚠️ Motivos")
for e in erros:
    st.write("-", e)

# ======================
# BACKTEST
# ======================

if st.button("📊 Backtest 30 dias (08h às 12h)"):

    wins, loss, erros_log = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("Resultado")

    st.write("Wins:", wins)
    st.write("Loss:", loss)
    st.write(f"Assertividade: {taxa:.2f}%")

    st.subheader("Erros mais comuns")
    for e in set(erros_log):
        st.write("-", e)

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
