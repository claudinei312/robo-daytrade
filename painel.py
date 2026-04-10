import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
import datetime
from streamlit_autorefresh import st_autorefresh

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô apenas", layout="wide")
st.title("🤖 Robô apenas")

ATIVO = "EUR/USD"

st_autorefresh(interval=10000, key="refresh")

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
        df[c] = pd.to_numeric(df[c])

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
# SUPORTE / RESISTÊNCIA
# ======================

def zonas(df):

    ult = df.tail(144)

    sup = ult["low"].min()
    res = ult["high"].max()

    return sup, res

# ======================
# ESTRATÉGIA
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

    # FILTRO DE TENDÊNCIA
    if trend == "ALTA":
        score += 1
    elif trend == "BAIXA":
        score -= 1
    else:
        erros.append("Mercado lateral")

    # EMA
    if df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        score += 1
    else:
        erros.append("EMA contra")

    # RSI
    if df["RSI"].iloc[-1] > 50:
        score += 1
    else:
        erros.append("RSI fraco")

    # MACD
    if df["macd"].iloc[-1] > 0:
        score += 1
    else:
        erros.append("MACD contra")

    # SUPORTE
    if abs(preco - sup) < (res - sup)*0.3:
        score += 1
    else:
        erros.append("Longe do suporte")

    # DECISÃO
    if score >= 4:
        return "COMPRA", erros

    if score <= -3:
        return "VENDA", erros

    return "AGUARDAR", erros

# ======================
# BACKTEST
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

        sinal, erros = analisar(sub)

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

sinal, erros = analisar(df)

preco = df["close"].iloc[-1]

st.metric("Preço atual", preco)

if sinal == "COMPRA":
    st.success("🟢 COMPRA")

elif sinal == "VENDA":
    st.error("🔴 VENDA")

else:
    st.warning("⚪ AGUARDAR")

# ======================
# BOTÃO BACKTEST
# ======================

if st.button("📊 Rodar Backtest 30 dias"):

    wins, loss, erros_log = backtest(df)

    total = wins + loss

    if total > 0:
        taxa = wins / total * 100
    else:
        taxa = 0

    st.subheader("📈 Resultado")

    st.write("Wins:", wins)
    st.write("Loss:", loss)
    st.write(f"Acurácia: {taxa:.2f}%")

    st.subheader("⚠️ Erros detectados")

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

st.plotly_chart(fig, use_container_width=True)======================

@st.cache_data(ttl=300)
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

    return df.dropna()

# ======================
# 🔍 SUPORTE/RESISTÊNCIA (3 TOQUES)
# ======================

def detectar_zonas(df):

    ultimos = df.tail(144)
    preco = ultimos["close"].iloc[-1]

    tolerancia = preco * 0.0008

    resistencias = []
    suportes = []

    highs = ultimos["high"]
    lows = ultimos["low"]

    for nivel in highs:
        toques = sum(abs(highs - nivel) < tolerancia)
        if toques >= 3:
            resistencias.append(nivel)

    for nivel in lows:
        toques = sum(abs(lows - nivel) < tolerancia)
        if toques >= 3:
            suportes.append(nivel)

    resistencia = max(resistencias) if resistencias else highs.max()
    suporte = min(suportes) if suportes else lows.min()

    return suporte, resistencia

# ======================
# 🔁 PULLBACK
# ======================

def detectar_pullback(df):

    preco = df["close"].iloc[-1]
    anterior = df["close"].iloc[-2]
    ema9 = df["EMA9"].iloc[-1]

    pullback_compra = anterior < ema9 and preco > ema9
    pullback_venda = anterior > ema9 and preco < ema9

    return pullback_compra, pullback_venda

# ======================
# 🧠 ESTRATÉGIA
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    preco = df["close"].iloc[-1]
    ema9 = df["EMA9"].iloc[-1]
    ema21 = df["EMA21"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    suporte, resistencia = detectar_zonas(df)

    zona = (resistencia - suporte) * 0.25

    perto_suporte = abs(preco - suporte) < zona
    perto_resistencia = abs(preco - resistencia) < zona

    tendencia_alta = ema9 > ema21
    tendencia_baixa = ema9 < ema21

    pullback_compra, pullback_venda = detectar_pullback(df)

    volatilidade = df["high"].tail(144).max() - df["low"].tail(144).min()

    if volatilidade < preco * 0.002:
        return "AGUARDAR", preco, 0, 0, suporte, resistencia, "Mercado lateral"

    # COMPRA
    if tendencia_alta and perto_suporte and pullback_compra and rsi > 50:
        stop = suporte
        alvo = preco + (resistencia - preco) * 0.7
        return "COMPRA", preco, stop, alvo, suporte, resistencia, "Pullback no suporte"

    # VENDA
    if tendencia_baixa and perto_resistencia and pullback_venda and rsi < 50:
        stop = resistencia
        alvo = preco - (preco - suporte) * 0.7
        return "VENDA", preco, stop, alvo, suporte, resistencia, "Pullback na resistência"

    return "AGUARDAR", preco, 0, 0, suporte, resistencia, "Sem confluência"

# ======================
# 📊 BACKTEST
# ======================

def backtest(df):

    wins = 0
    loss = 0

    erros = {
        "lateral": 0,
        "sem_confluencia": 0,
        "stop": 0
    }

    for i in range(200, len(df)-10):

        hora = df.loc[i, "datetime"].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, preco, stop, alvo, sup, res, motivo = analisar(sub)

        if sinal == "AGUARDAR":
            if motivo == "Mercado lateral":
                erros["lateral"] += 1
            else:
                erros["sem_confluencia"] += 1
            continue

        futuro = df.iloc[i:i+10]

        if sinal == "COMPRA":
            if futuro["high"].max() >= alvo:
                wins += 1
            elif futuro["low"].min() <= stop:
                loss += 1
                erros["stop"] += 1

        if sinal == "VENDA":
            if futuro["low"].min() <= alvo:
                wins += 1
            elif futuro["high"].max() >= stop:
                loss += 1
                erros["stop"] += 1

    return wins, loss, erros

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

sinal, preco, stop, alvo, suporte, resistencia, motivo = analisar(df)

st.subheader(f"📊 {ATIVO}")
st.metric("Preço atual", round(preco, 5))
st.write("📌 Status:", motivo)

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

fig.add_hline(y=suporte, line_dash="dot")
fig.add_hline(y=resistencia, line_dash="dot")

fig.update_layout(template="plotly_dark", height=500)

st.plotly_chart(fig, use_container_width=True)

# ======================
# SINAL
# ======================

if sinal == "COMPRA":
    st.success(f"🟢 COMPRA\nEntrada: {preco}\nStop: {stop}\nAlvo: {alvo}")
elif sinal == "VENDA":
    st.error(f"🔴 VENDA\nEntrada: {preco}\nStop: {stop}\nAlvo: {alvo}")
else:
    st.info("⚪ AGUARDAR")

# ======================
# BACKTEST BOTÃO
# ======================

if st.button("📊 Rodar Backtest 30 dias (08h–12h)"):

    w, l, erros = backtest(df)
    total = w + l

    st.success(f"""
📊 RESULTADO

Wins: {w}
Loss: {l}
Winrate: {round((w/total)*100,2) if total>0 else 0}%

Erros:
- Mercado lateral: {erros['lateral']}
- Sem confluência: {erros['sem_confluencia']}
- Stop atingido: {erros['stop']}
""")
