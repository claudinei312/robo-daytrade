import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
from streamlit_autorefresh import st_autorefresh

# ======================
# 🎨 CONFIG
# ======================
st.set_page_config(page_title="Sniper Pro Trading", layout="wide")

st.title("📊 SNIPER PRO TRADING DESK")

# ======================
# 🔐 KEYS
# ======================
API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]
BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

td = TDClient(apikey=API_KEY)

ativos = ["USD/JPY:FX"]

# ======================
# 🔁 AUTO REFRESH
# ======================
st_autorefresh(interval=5000, key="refresh")

# ======================
# 📲 TELEGRAM
# ======================
def telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

# ======================
# 📲 TESTE TELEGRAM
# ======================
st.sidebar.subheader("📲 Telegram Teste")

if st.sidebar.button("Testar Telegram"):
    telegram("🚨 TESTE OK: Bot funcionando corretamente ✔️")
    st.sidebar.success("Enviado com sucesso!")

# ======================
# 📥 DADOS
# ======================
@st.cache_data(ttl=240)
def pegar_dados(ativo):
    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=500
    ).as_pandas()

    df = df[::-1].reset_index()

    df["datetime"] = pd.to_datetime(df["datetime"])
    df["datetime"] = df["datetime"].dt.tz_localize("UTC").dt.tz_convert("America/Sao_Paulo")

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 ESTRATÉGIA ORIGINAL (NÃO ALTERADA)
# ======================
def analisar(df):

    df["MA9"] = SMAIndicator(df["close"], 9).sma_indicator()
    df["MA21"] = SMAIndicator(df["close"], 21).sma_indicator()

    preco = df["close"].iloc[-1]
    ma9 = df["MA9"].iloc[-1]
    ma21 = df["MA21"].iloc[-1]

    suporte = df["low"].rolling(20).min().iloc[-1]
    resistencia = df["high"].rolling(20).max().iloc[-1]

    tendencia = abs(ma9 - ma21) > 0.00025

    body = abs(df["close"].iloc[-1] - df["open"].iloc[-1])
    rng = df["high"].iloc[-1] - df["low"].iloc[-1]

    candle_ok = body > rng * 0.6

    vol = df["high"].rolling(10).max().iloc[-1] - df["low"].rolling(10).min().iloc[-1]
    vol_ok = vol > preco * 0.0005

    if not (tendencia and candle_ok and vol_ok):
        return "AGUARDAR", preco, 0, 0

    if ma9 > ma21 and preco <= suporte * 1.001:
        return "COMPRA", preco, suporte, preco + (preco - suporte) * 2

    if ma9 < ma21 and preco >= resistencia * 0.999:
        return "VENDA", preco, resistencia, preco - (resistencia - preco) * 2

    return "AGUARDAR", preco, 0, 0

# ======================
# 📊 BACKTEST PRO REAL (CORRIGIDO)
# ======================
def backtest(df):

    df = df.copy()
    df = df[(df["datetime"].dt.hour >= 8) & (df["datetime"].dt.hour <= 12)]

    wins = 0
    losses = 0
    trades = 0

    erros = {
        "LATERAL": 0,
        "STOP": 0,
        "FRACA_TENDENCIA": 0,
        "FALHA_ROMPIMENTO": 0
    }

    detalhes_erros = []

    horarios = {}

    for i in range(50, len(df)):

        sub = df.iloc[:i]
        sinal, preco, stop, alvo = analisar(sub)

        if sinal not in ["COMPRA", "VENDA"]:
            continue

        trades += 1

        hora = df.iloc[i]["datetime"].hour
        horarios.setdefault(hora, {"wins":0,"loss":0,"trades":0})
        horarios[hora]["trades"] += 1

        futuro = df.iloc[i:i+5]

        if len(futuro) == 0:
            continue

        max_price = futuro["high"].max()
        min_price = futuro["low"].min()

        resultado = None
        motivo = ""

        if sinal == "COMPRA":

            if max_price >= alvo:
                wins += 1
                horarios[hora]["wins"] += 1
                continue

            if min_price <= stop:
                losses += 1
                erros["STOP"] += 1
                motivo = "Stop loss atingido antes do alvo"
            
            elif max_price < alvo:
                losses += 1
                erros["LATERAL"] += 1
                motivo = "Preço não teve força suficiente (mercado lateral)"

        if sinal == "VENDA":

            if min_price <= alvo:
                wins += 1
                horarios[hora]["wins"] += 1
                continue

            if max_price >= stop:
                losses += 1
                erros["STOP"] += 1
                motivo = "Stop loss atingido antes do alvo"

            elif min_price > alvo:
                losses += 1
                erros["FRACA_TENDENCIA"] += 1
                motivo = "Movimento fraco contra tendência"

        detalhes_erros.append(motivo)

        horarios[hora]["loss"] += 1

    return wins, losses, trades, erros, horarios, detalhes_erros

# ======================
# 📥 DADOS
# ======================
dados = {ativos[0]: pegar_dados(ativos[0])}

df = dados["USD/JPY:FX"]

# ======================
# 📊 BACKTEST BOTÃO
# ======================
st.divider()

if st.button("📊 Rodar Backtest PRO COMPLETO"):

    w, l, t, erros, horarios, detalhes = backtest(df)

    st.success("Backtest concluído!")

    st.metric("Trades", t)
    st.metric("Wins", w)
    st.metric("Losses", l)
    st.metric("Win Rate", f"{(w/t)*100:.2f}%" if t > 0 else "0%")

    st.divider()

    st.subheader("❌ Diagnóstico de Erros")

    total = sum(erros.values())

    for k, v in erros.items():
        perc = (v / total * 100) if total > 0 else 0
        st.write(f"- {k}: {perc:.2f}%")

    st.divider()

    st.subheader("🧠 Motivos reais dos erros")

    for d in list(set(detalhes))[:10]:
        st.write("•", d)

    st.divider()

    st.subheader("⏱ Performance por horário")

    for h in sorted(horarios.keys()):
        d = horarios[h]
        wr = (d["wins"]/d["trades"])*100 if d["trades"] > 0 else 0
        st.write(f"{h}:00 → WinRate {wr:.2f}% | Trades {d['trades']}")

# ======================
# 📊 GRÁFICO + SINAL
# ======================
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["datetime"],
    open=df["open"],
    high=df["high"],
    low=df["low"],
    close=df["close"]
))

st.plotly_chart(fig, use_container_width=True)

sinal, preco, stop, alvo = analisar(df)

st.subheader("📡 SINAL ATUAL")
st.write(sinal)
st.write("Preço:", preco)

# ======================
# 📲 TELEGRAM REAL
# ======================
agora = datetime.datetime.now()

if sinal in ["COMPRA", "VENDA"]:
    telegram(f"""
🚨 SNIPER PRO TRADE

📊 Ativo: USD/JPY
📈 Sinal: {sinal}

💰 Preço: {preco}
🎯 Entrada: {preco}
🛑 Stop: {stop}
🏁 Alvo: {alvo}

⏱ {agora.strftime('%H:%M:%S')}
""")
