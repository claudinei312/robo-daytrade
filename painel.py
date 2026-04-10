import streamlit as st
from twelvedata import TDClient
import pandas as pd
import requests
from ta.trend import SMAIndicator
import plotly.graph_objects as go
import datetime
import time
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

div[data-testid="stMetric"] {
    background-color: #0f172a;
    border-radius: 10px;
    padding: 8px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>📊 SNIPER PRO TRADING DESK</div>", unsafe_allow_html=True)

# ======================
# 🔐 CONFIG (SEGURA)
# ======================
API_KEY = st.secrets["API_KEY"]
NEWS_API = st.secrets["NEWS_API"]

BOT_TOKEN = st.secrets["BOT_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

td = TDClient(apikey=API_KEY)

# ======================
# 🎯 ATIVOS
# ======================
ativos = ["USD/JPY:FX"]

# ======================
# 🔁 AUTO REFRESH
# ======================
st_autorefresh(interval=5000, key="refresh")

rodando = st.toggle("🟢 Ativar Robô", value=True)
if not rodando:
    st.stop()

# ======================
# 📩 TELEGRAM PROFISSIONAL
# ======================
def telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload)
    except:
        pass

# ======================
# ⏱ TIMER
# ======================
def tempo_candle():
    agora = datetime.datetime.utcnow()
    minuto = agora.minute % 5
    segundo = agora.second
    return f"{4 - minuto:02d}:{59 - segundo:02d}"

# ======================
# 📰 NOTÍCIAS
# ======================
@st.cache_data(ttl=300)
def noticias():
    url = f"https://newsapi.org/v2/everything?q=forex OR USD OR JPY&language=en&pageSize=5&apiKey={NEWS_API}"
    try:
        return requests.get(url).json().get("articles", [])
    except:
        return []

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

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
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
# 📊 BACKTEST (15 DIAS - 08H ÀS 12H)
# ======================
def backtest(df):

    df = df.copy()
    df = df[(df["datetime"].dt.hour >= 8) & (df["datetime"].dt.hour <= 12)]

    wins = 0
    losses = 0
    trades = 0

    for i in range(50, len(df)):

        sub = df.iloc[:i].copy()
        sinal, preco, stop, alvo = analisar(sub)

        if sinal in ["COMPRA", "VENDA"]:
            trades += 1

            futuro = df.iloc[i:i+5]

            if len(futuro) == 0:
                continue

            max_price = futuro["high"].max()
            min_price = futuro["low"].min()

            if sinal == "COMPRA":
                if max_price >= alvo:
                    wins += 1
                elif min_price <= stop:
                    losses += 1

            if sinal == "VENDA":
                if min_price <= alvo:
                    wins += 1
                elif max_price >= stop:
                    losses += 1

    return wins, losses, trades

# ======================
# 📥 ESTADO
# ======================
if "sinais" not in st.session_state:
    st.session_state.sinais = {}

if "ultimo_status" not in st.session_state:
    st.session_state.ultimo_status = {}

# ======================
# 📥 DADOS
# ======================
dados = {ativo: pegar_dados(ativo) for ativo in ativos}

# ======================
# 📊 BACKTEST BOTÃO
# ======================
st.divider()

if st.button("📊 Rodar Backtest (15 dias / 08-12)"):

    with st.spinner("Executando backtest..."):

        df_bt = dados["USD/JPY:FX"]

        w, l, t = backtest(df_bt)

        st.success("Backtest concluído!")

        st.metric("Trades", t)
        st.metric("Wins", w)
        st.metric("Losses", l)

        if t > 0:
            st.metric("Win Rate", f"{(w/t)*100:.2f}%")

# ======================
# 📊 LOOP PRINCIPAL
# ======================
for ativo in ativos:

    st.markdown("---")

    df = dados[ativo]
    sinal, preco, stop, alvo = analisar(df)
    agora = datetime.datetime.now()

    # ======================
    # 🚨 TELEGRAM PROFISSIONAL
    # ======================
    if sinal in ["COMPRA", "VENDA"]:

        if ativo not in st.session_state.sinais or st.session_state.sinais[ativo]["tipo"] != sinal:

            st.session_state.sinais[ativo] = {
                "tipo": sinal,
                "entrada_hora": agora,
                "preco_entrada": preco,
                "preco_saida": alvo
            }

            telegram(f"""
🚨 <b>SNIPER PRO TRADE</b>

📊 Ativo: {ativo}
📈 Direção: {sinal}

💰 Preço atual: {preco}
🎯 Entrada: {preco}
🛑 Stop: {stop}
🏁 Alvo: {alvo}

⏱ Horário: {agora.strftime('%H:%M:%S')}

🧠 Estratégia: MA9 x MA21 + Suporte/Resistência
""")

    # ======================
    # 📊 STATUS (ANTI-SPAM)
    # ======================
    ultimo = st.session_state.ultimo_status.get(ativo)

    if not ultimo or (agora - ultimo).seconds >= 300:

        st.session_state.ultimo_status[ativo] = agora

        telegram(f"""
📊 <b>STATUS</b>

📌 {ativo}
💰 Preço: {preco}
📈 Sinal: {sinal}
""")

    # ======================
    # 📊 VISUAL
    # ======================
    st.subheader(ativo)

    st.metric("Preço", preco)
    st.info(f"⏱ Candle fecha em: {tempo_candle()}")

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["datetime"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"]
    ))

    fig.update_layout(template="plotly_dark", height=420, xaxis_rangeslider_visible=False)

    st.plotly_chart(fig, use_container_width=True)

    # ======================
    # 📌 SINAL ATUAL
    # ======================
    info = st.session_state.sinais.get(ativo, None)

    if info:

        entrada = info["entrada_hora"]
        saida = entrada + datetime.timedelta(minutes=5)

        st.markdown("### 📊 SINAL ATUAL")

        st.write(f"📌 Direção: {info['tipo']}")
        st.write(f"💰 Entrada: {info['preco_entrada']}")
        st.write(f"🎯 Saída: {info['preco_saida']}")
        st.write(f"🟢 Entrada: {entrada.strftime('%H:%M:%S')}")
        st.write(f"🔴 Saída: {saida.strftime('%H:%M:%S')}")

    else:
        st.info("📌 AGUARDANDO OPORTUNIDADE")

    # ======================
    # ALERTAS VISUAIS
    # ======================
    if sinal == "COMPRA":
        st.success("🟢 COMPRA")
    elif sinal == "VENDA":
        st.error("🔴 VENDA")
    else:
        st.info("⚪ AGUARDAR")

# ======================
# 📰 NOTÍCIAS
# ======================
st.divider()
st.subheader("📰 Notícias")

for n in noticias():
    st.write("🗞️", n["title"])
