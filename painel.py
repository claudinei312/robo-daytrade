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
        outputsize=5000
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna().reset_index(drop=True)

# ======================
# TENDÊNCIA 1H (IMPORTANTE)
# ======================

def tendencia_1h(df):
    df["EMA50"] = EMAIndicator(df["close"], 50).ema_indicator()
    df["EMA200"] = EMAIndicator(df["close"], 200).ema_indicator()

    ema50 = df["EMA50"].iloc[-1]
    ema200 = df["EMA200"].iloc[-1]

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
    return ult["low"].min(), ult["high"].max()

# ======================
# VELA FORTE
# ======================

def vela_forte(df):
    candle = df.iloc[-1]

    corpo = abs(candle["close"] - candle["open"])
    range_total = candle["high"] - candle["low"]

    if range_total == 0:
        return False

    return corpo / range_total > 0.6

# ======================
# PULLBACK SIMPLES
# ======================

def pullback(df, suporte, resistencia):
    preco = df["close"].iloc[-1]

    dist_sup = abs(preco - suporte)
    dist_res = abs(preco - resistencia)

    # perto de suporte ou resistência
    return dist_sup < dist_res

# ======================
# ESTRATÉGIA
# ======================

def analisar(df):

    df["EMA9"] = EMAIndicator(df["close"], 9).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    macd = MACD(df["close"])
    df["macd"] = macd.macd()

    preco = df["close"].iloc[-1]
    sup, res = zonas(df)

    trend = tendencia_1h(df)

    score = 0
    erros = []

    # ======================
    # CONTEXTO 1H
    # ======================

    if trend == "ALTA":
        score += 1
    elif trend == "BAIXA":
        score -= 1
    else:
        erros.append("Mercado lateral")

    # ======================
    # EMA (entrada)
    # ======================

    if df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        score += 1
    else:
        erros.append("EMA contra")

    # ======================
    # MACD
    # ======================

    if df["macd"].iloc[-1] > 0:
        score += 1
    else:
        erros.append("MACD contra")

    # ======================
    # VELA FORTE
    # ======================

    if vela_forte(df):
        score += 1
    else:
        erros.append("Sem vela forte")

    # ======================
    # PULLBACK
    # ======================

    if pullback(df, sup, res):
        score += 1
    else:
        erros.append("Sem pullback")

    # ======================
    # DECISÃO
    # ======================

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    if score >= 4:
        return "COMPRA", preco, entrada, saida, erros

    if score <= 1:
        return "VENDA", preco, entrada, saida, erros

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST
# ======================

def backtest(df):

    wins = 0
    loss = 0
    erros_log = []

    for i in range(200, len(df) - 1):

        sub = df.iloc[:i]

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entrada = df["close"].iloc[i]
        saida = df["close"].iloc[i + 1]

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

trend = tendencia_1h(df)
st.write("📊 Tendência 1H:", trend)

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

if st.button("📊 Rodar Backtest"):

    wins, loss, erros_log = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("📈 Resultado")

    st.write("✅ Wins:", wins)
    st.write("❌ Loss:", loss)
    st.write(f"🎯 Assertividade: {taxa:.2f}%")

    st.subheader("⚠️ Erros mais comuns")

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
