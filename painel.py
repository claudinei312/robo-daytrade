import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator, MACD, ADXIndicator
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

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna().reset_index(drop=True)

# ======================
# TENDÊNCIA
# ======================

def tendencia(df):
    ema50 = EMAIndicator(df["close"], 50).ema_indicator().iloc[-1]
    ema200 = EMAIndicator(df["close"], 200).ema_indicator().iloc[-1]

    if ema50 > ema200:
        return "ALTA"
    elif ema50 < ema200:
        return "BAIXA"
    return "LATERAL"

# ======================
# SUPORTE / RESISTÊNCIA
# ======================

def zonas(df):
    ult = df.tail(144)
    suporte = ult["low"].min()
    resistencia = ult["high"].max()
    return suporte, resistencia

# ======================
# ESTRATÉGIA
# ======================

def analisar(df):

    df = df.dropna()

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()
    df["macd"] = MACD(df["close"]).macd()
    df["adx"] = ADXIndicator(df["high"], df["low"], df["close"], 14).adx()

    preco = df["close"].iloc[-1]
    sup, res = zonas(df)
    trend = tendencia(df)

    score = 0
    erros = []

    # ======================
    # ADX FILTRO
    # ======================

    adx_val = df["adx"].iloc[-1]

    if pd.isna(adx_val):
        return "AGUARDAR", preco, None, None, ["ADX inválido"]

    if adx_val < 20:
        return "AGUARDAR", preco, None, None, ["Mercado lateral (ADX baixo)"]

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
    # RSI (OPÇÃO 3)
    # ======================

    rsi = df["RSI"].iloc[-1]

    if trend == "ALTA":
        if 50 <= rsi <= 70:
            score += 1
        else:
            erros.append(f"RSI fora compra ({rsi:.2f})")

    elif trend == "BAIXA":
        if 30 <= rsi <= 50:
            score += 1
        else:
            erros.append(f"RSI fora venda ({rsi:.2f})")

    # ======================
    # MACD
    # ======================

    if df["macd"].iloc[-1] > 0:
        score += 1
    else:
        erros.append("MACD contra")

    # ======================
    # SUPORTE
    # ======================

    if abs(preco - sup) < (res - sup) * 0.3:
        score += 1
    else:
        erros.append("Longe do suporte")

    # ======================
    # DECISÃO
    # ======================

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if score >= 4:
        return "COMPRA", preco, entrada, saida, erros

    if score <= -3:
        return "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST COM LOG COMPLETO (CORRIGIDO)
# ======================

def backtest(df):

    df = df.dropna().reset_index(drop=True)

    # pré-cálculo (performance)
    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()
    df["macd"] = MACD(df["close"]).macd()
    df["adx"] = ADXIndicator(df["high"], df["low"], df["close"], 14).adx()

    wins = 0
    loss = 0
    logs = []

    for i in range(200, len(df) - 2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 12:
            continue

        adx_val = df["adx"].iloc[i]

        if pd.isna(adx_val) or adx_val < 20:
            continue

        ema9 = df["EMA9"].iloc[i]
        ema21 = df["EMA21"].iloc[i]
        rsi = df["RSI"].iloc[i]
        macd = df["macd"].iloc[i]

        preco = df["close"].iloc[i]
        saida = df["close"].iloc[i + 1]

        sup = df["low"].tail(144).min()
        res = df["high"].tail(144).max()

        score = 0
        erros = []

        if ema9 > ema21:
            score += 1
            trend = "ALTA"
        else:
            trend = "BAIXA"
            erros.append("EMA contra")

        if trend == "ALTA":
            if 50 <= rsi <= 70:
                score += 1
            else:
                erros.append("RSI fora compra")
        else:
            if 30 <= rsi <= 50:
                score += 1
            else:
                erros.append("RSI fora venda")

        if macd > 0:
            score += 1
        else:
            erros.append("MACD contra")

        range_total = res - sup
        dist = abs(preco - sup)

        if range_total > 0 and dist < range_total * 0.3:
            score += 1
        else:
            erros.append("Longe do suporte")

        resultado = None

        if score >= 4:
            if saida > preco:
                wins += 1
                resultado = "WIN"
            else:
                loss += 1
                resultado = "LOSS"

        elif score <= -3:
            if saida < preco:
                wins += 1
                resultado = "WIN"
            else:
                loss += 1
                resultado = "LOSS"

        if resultado:
            logs.append({
                "hora": df["datetime"].iloc[i],
                "resultado": resultado,
                "preco": preco,
                "saida": saida,
                "rsi": rsi,
                "adx": adx_val,
                "macd": macd,
                "score": score,
                "erros": erros
            })

    return wins, loss, logs

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

trend = tendencia(df)
st.write("📊 Tendência:", trend)

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("💰 Preço atual", preco)

if sinal == "COMPRA":
    st.success(f"🟢 COMPRA\nEntrada: {entrada.strftime('%H:%M')}\nSaída: {saida.strftime('%H:%M')}")
elif sinal == "VENDA":
    st.error(f"🔴 VENDA\nEntrada: {entrada.strftime('%H:%M')}\nSaída: {saida.strftime('%H:%M')}")
else:
    st.warning("⚪ AGUARDAR")

st.subheader("⚠️ Motivos atuais")
for e in erros:
    st.write("-", e)

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest 30 dias"):

    wins, loss, logs = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("📈 Resultado")
    st.write("✅ Wins:", wins)
    st.write("❌ Loss:", loss)
    st.write(f"🎯 Assertividade: {taxa:.2f}%")

    st.subheader("⚠️ Detalhes dos Loss (diagnóstico real)")

    for l in logs[:15]:
        st.write("-----")
        st.write("Resultado:", l["resultado"])
        st.write("Score:", l["score"])
        st.write("RSI:", l["rsi"])
        st.write("ADX:", l["adx"])
        st.write("MACD:", l["macd"])
        st.write("Erros:", l["erros"])

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
