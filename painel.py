import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import datetime
from streamlit_autorefresh import st_autorefresh

# ======================
# 🎨 LAYOUT ORIGINAL
# ======================

st.set_page_config(page_title="Sniper Pro Trading", layout="wide")

st.markdown("""
<style>  
body { background-color: #0b0f19; }  
.main-title {  
    font-size: 34px;  
    font-weight: 800;  
    text-align: center;  
    color: #00ff99;  
    margin-bottom: 15px;  
}  
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>📊 SNIPER PRO TRADING DESK</div>", unsafe_allow_html=True)

# ======================
# 🔐 CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

ATIVO = "EUR/USD"

st_autorefresh(interval=8000, key="refresh")

rodando = st.toggle("🟢 Ativar Robô", value=True)
if not rodando:
    st.stop()

# ======================
# 📥 DADOS
# ======================

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
