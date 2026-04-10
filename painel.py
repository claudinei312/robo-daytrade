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
# SUPORTE / RESISTÊNCIA
# ======================

def zonas(df):
    ult = df.tail(144)
    return ult["low"].min(), ult["high"].max()

# ======================
# ESTRATÉGIA (INALTERADA)
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

    if trend == "ALTA":
        score += 1
    elif trend == "BAIXA":
        score -= 1
    else:
        erros.append("Mercado lateral")

    if df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        score += 1
    else:
        erros.append("EMA contra")

    if df["RSI"].iloc[-1] > 50:
        score += 1
    else:
        erros.append("RSI fraco")

    if df["macd"].iloc[-1] > 0:
        score += 1
    else:
        erros.append("MACD contra")

    if abs(preco - sup) < (res - sup)*0.3:
        score += 1
    else:
        erros.append("Longe do suporte")

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if score >= 4:
        return "COMPRA", preco, entrada, saida, erros

    if score <= -3:
        return "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# 🔥 BACKTEST PROFISSIONAL (SUBSTITUÍDO)
# ======================

def backtest(df):

    wins = 0
    loss = 0
    trades = []

    df = df.copy().reset_index(drop=True)

    # ======================
    # LOOP PROFISSIONAL
    # ======================

    for i in range(200, len(df) - 2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i]

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        # EXECUÇÃO REALISTA (SEM CLOSE FALSO)
        entry = df["open"].iloc[i + 1]
        exit_ = df["open"].iloc[i + 2]

        if sinal == "COMPRA":
            result = "WIN" if exit_ > entry else "LOSS"
        elif sinal == "VENDA":
            result = "WIN" if exit_ < entry else "LOSS"
        else:
            continue

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

st.metric("💰 Preço atual", preco)

# ======================
# SINAL
# ======================

if sinal == "COMPRA":
    st.success(f"""
🟢 COMPRA

Entrada: {entrada.strftime('%H:%M')}
Saída: {saida.strftime('%H:%M')}
""")

elif sinal == "VENDA":
    st.error(f"""
🔴 VENDA

Entrada: {entrada.strftime('%H:%M')}
Saída: {saida.strftime('%H:%M')}
""")

else:
    st.warning("⚪ AGUARDAR")

# ======================
# ERROS
# ======================

st.subheader("⚠️ Motivos para não entrar forte")

for e in erros:
    st.write("-", e)

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest 30 dias (08h às 12h)"):

    wins, loss, trades = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total else 0

    st.subheader("📈 Resultado")

    st.write("✅ Wins:", wins)
    st.write("❌ Loss:", loss)
    st.write(f"🎯 Assertividade: {taxa:.2f}%")

    st.subheader("⚠️ Últimos trades")

    for t in trades[:15]:
        st.write("----")
        st.write("Sinal:", t["signal"])
        st.write("Resultado:", t["result"])
        st.write("Entry:", t["entry"])
        st.write("Exit:", t["exit"])
        st.write("Erros:", t["erros"])

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
