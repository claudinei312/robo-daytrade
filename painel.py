import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
from streamlit_autorefresh import st_autorefresh

# ======================
# 🎨 LAYOUT
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

rodando = st.toggle("🟢 Ativar Robô", value=True)
if not rodando:
    st.stop()

# ======================
# 📲 TELEGRAM PROFISSIONAL
# ======================
def telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except:
        pass

# ======================
# 📲 BOTÃO TESTE TELEGRAM
# ======================
st.sidebar.subheader("📲 Teste Telegram")

if st.sidebar.button("Enviar teste Telegram"):
    telegram("🚨 TESTE: seu bot está funcionando corretamente ✔️")
    st.sidebar.success("Mensagem enviada!")

# ======================
# ⏱ TIMER
# ======================
def tempo_candle():
    agora = datetime.datetime.utcnow()
    minuto = agora.minute % 5
    segundo = agora.second
    return f"{4 - minuto:02d}:{59 - segundo:02d}"

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
    df["datetime"] = df["datetime"].dt.tz_localize("UTC")
    df["datetime"] = df["datetime"].dt.tz_convert("America/Sao_Paulo")

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# 🧠 ESTRATÉGIA (NÃO ALTERADA)
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

    candle = body > rng * 0.6

    vol = df["high"].rolling(10).max().iloc[-1] - df["low"].rolling(10).min().iloc[-1]
    vol_ok = vol > preco * 0.0005

    if not tendencia or not candle or not vol_ok:
        return "AGUARDAR", preco, 0, 0

    if ma9 > ma21 and preco <= suporte * 1.001:
        return "COMPRA", preco, suporte, preco + (preco - suporte) * 2

    if ma9 < ma21 and preco >= resistencia * 0.999:
        return "VENDA", preco, resistencia, preco - (resistencia - preco) * 2

    return "AGUARDAR", preco, 0, 0

# ======================
# 📊 BACKTEST PRO
# ======================
def backtest(df):

    df = df.copy()
    df = df[(df["datetime"].dt.hour >= 8) & (df["datetime"].dt.hour <= 12)]

    wins = 0
    losses = 0
    trades = 0

    erros = {"STOP":0,"LATERAL":0,"FRACO":0,"ALVO":0}
    horarios = {}

    for i in range(50, len(df)):

        sub = df.iloc[:i].copy()
        sinal, preco, stop, alvo = analisar(sub)

        if sinal in ["COMPRA","VENDA"]:
            trades += 1

            hora = df.iloc[i]["datetime"].hour
            horarios.setdefault(hora, {"wins":0,"loss":0,"trades":0})
            horarios[hora]["trades"] += 1

            futuro = df.iloc[i:i+5]
            if len(futuro) == 0:
                continue

            max_price = futuro["high"].max()
            min_price = futuro["low"].min()

            if sinal == "COMPRA":
                if max_price >= alvo:
                    wins += 1
                    erros["ALVO"] += 1
                    horarios[hora]["wins"] += 1
                elif min_price <= stop:
                    losses += 1
                    erros["STOP"] += 1
                    horarios[hora]["loss"] += 1
                else:
                    losses += 1
                    erros["LATERAL"] += 1
                    horarios[hora]["loss"] += 1

            if sinal == "VENDA":
                if min_price <= alvo:
                    wins += 1
                    erros["ALVO"] += 1
                    horarios[hora]["wins"] += 1
                elif max_price >= stop:
                    losses += 1
                    erros["STOP"] += 1
                    horarios[hora]["loss"] += 1
                else:
                    losses += 1
                    erros["FRACO"] += 1
                    horarios[hora]["loss"] += 1

    return wins, losses, trades, erros, horarios

# ======================
# 📥 DADOS
# ======================
dados = {ativo: pegar_dados(ativo) for ativo in ativos}

# ======================
# 📊 BACKTEST BOTÃO
# ======================
st.divider()

if st.button("📊 Rodar Backtest PRO (15 dias / 08-12)"):

    df_bt = dados["USD/JPY:FX"]

    w,l,t,erros,horarios = backtest(df_bt)

    st.success("Backtest concluído!")

    st.metric("Trades", t)
    st.metric("Wins", w)
    st.metric("Losses", l)
    st.metric("Win Rate", f"{(w/t)*100:.2f}%" if t>0 else "0%")

    st.divider()
    st.subheader("📉 Erros")

    st.write(erros)

    st.divider()
    st.subheader("⏱ Performance por Hora")

    for h in sorted(horarios.keys()):
        d = horarios[h]
        wr = (d["wins"]/d["trades"])*100 if d["trades"]>0 else 0
        st.write(f"{h}:00 → Trades: {d['trades']} | WinRate: {wr:.2f}%")

# ======================
# 📊 LOOP PRINCIPAL
# ======================
for ativo in ativos:

    st.markdown("---")

    df = dados[ativo]
    sinal, preco, stop, alvo = analisar(df)
    agora = datetime.datetime.now()

    if sinal in ["COMPRA","VENDA"]:

        telegram(f"""
🚨 <b>SNIPER PRO TRADE</b>

📊 Ativo: {ativo}
📈 Direção: {sinal}

💰 Preço: {preco}
🎯 Entrada: {preco}
🛑 Stop: {stop}
🏁 Alvo: {alvo}

⏱ {agora.strftime('%H:%M:%S')}
""")

    st.metric("Preço", preco)
    st.write("Sinal:", sinal)
