import streamlit as st
from twelvedata import TDClient
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
import datetime

# ======================
# CONFIG API (INSERIDA)
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô Pro", layout="wide")
st.title("🤖 Robô Pro - Versão Completa")

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

    return df.dropna()

# ======================
# TENDÊNCIA
# ======================

def tendencia(df):
    df["EMA50"] = EMAIndicator(df["close"], 50).ema_indicator()
    df["EMA200"] = EMAIndicator(df["close"], 200).ema_indicator()

    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        return "ALTA"
    elif df["EMA50"].iloc[-1] < df["EMA200"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# SUPORTE / RESISTÊNCIA (2 TOQUES)
# ======================

def detectar_zonas(df, tol=0.0015):

    lows = df["low"].values
    highs = df["high"].values

    sup_zones = []
    res_zones = []

    # suporte
    for i in range(len(lows)):
        base = lows[i]
        touches = np.sum(np.abs(lows - base) / base < tol)

        if touches >= 2:
            sup_zones.append(base)

    # resistência
    for i in range(len(highs)):
        base = highs[i]
        touches = np.sum(np.abs(highs - base) / base < tol)

        if touches >= 2:
            res_zones.append(base)

    suporte = np.mean(sup_zones) if sup_zones else np.min(lows)
    resistencia = np.mean(res_zones) if res_zones else np.max(highs)

    return suporte, resistencia

# ======================
# ESTRATÉGIA
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()
    df["RSI"] = RSIIndicator(df["close"], 14).rsi()

    macd = MACD(df["close"])
    df["MACD"] = macd.macd()

    preco = df["close"].iloc[-1]
    sup, res = detectar_zonas(df)
    trend = tendencia(df)

    score = 0
    erros = []

    # tendência
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
    if df["MACD"].iloc[-1] > 0:
        score += 1
    else:
        erros.append("MACD contra")

    # filtro estrutura
    range_total = res - sup

    if range_total > 0:
        dist_sup = (preco - sup) / range_total
        dist_res = (res - preco) / range_total

        if dist_sup > 0.85:
            erros.append("Preço esticado (resistência próxima)")
        if dist_res > 0.85:
            erros.append("Preço esticado (suporte próximo)")

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if score >= 4:
        return "COMPRA", preco, entrada, saida, erros

    if score <= -3:
        return "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST
# ======================

def backtest(df):

    wins = 0
    loss = 0
    trades = []

    df = df.reset_index(drop=True)

    for i in range(200, len(df) - 2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entry = df["open"].iloc[i + 1]
        exit_ = df["open"].iloc[i + 2]

        if sinal == "COMPRA":
            result = "WIN" if exit_ > entry else "LOSS"
        else:
            result = "WIN" if exit_ < entry else "LOSS"

        if result == "WIN":
            wins += 1
        else:
            loss += 1

        trades.append({
            "time": df["datetime"].iloc[i],
            "signal": sinal,
            "result": result,
            "entry": entry,
            "exit": exit_,
            "erros": erros
        })

    return wins, loss, trades

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

trend = tendencia(df)
st.write("📊 Tendência:", trend)

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("💰 Preço atual", round(preco, 5))

if sinal == "COMPRA":
    st.success(f"🟢 COMPRA\nEntrada: {entrada}\nSaída: {saida}")

elif sinal == "VENDA":
    st.error(f"🔴 VENDA\nEntrada: {entrada}\nSaída: {saida}")

else:
    st.warning("⚪ AGUARDAR")

st.subheader("⚠️ Motivos de bloqueio")
for e in erros:
    st.write("•", e)

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest"):

    wins, loss, trades = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("📈 Resultado")

    st.write("✅ Wins:", wins)
    st.write("❌ Loss:", loss)
    st.write(f"🎯 Assertividade: {taxa:.2f}%")

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

fig.update_layout(height=600, template="plotly_dark")

st.plotly_chart(fig, use_container_width=True)
