import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator
import datetime

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Robô Cruzamento PURO", layout="wide")
st.title("🤖 EMA Cross PURO + Backtest PRO")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=800
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# ESTRATÉGIA PURO CRUZAMENTO
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    i = len(df) - 1
    erros = []

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        range_total = df["high"].iloc[i] - df["low"].iloc[i]
        if range_total == 0:
            return False
        return (corpo / range_total) > 0.5  # equilibrado

    # ======================
    # COMPRA
    # ======================

    if df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]:

        if vela_forte(i-1):
            if df["close"].iloc[i] > df["open"].iloc[i]:
                return "COMPRA", erros
            else:
                erros.append("Sem continuidade compra")
        else:
            erros.append("Sem força compra")

    # ======================
    # VENDA
    # ======================

    if df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]:

        if vela_forte(i-1):
            if df["close"].iloc[i] < df["open"].iloc[i]:
                return "VENDA", erros
            else:
                erros.append("Sem continuidade venda")
        else:
            erros.append("Sem força venda")

    erros.append("Sem setup")
    return "AGUARDAR", erros

# ======================
# BACKTEST PROFISSIONAL
# ======================

def backtest(df):

    wins = 0
    loss = 0
    log = []

    erros_stats = {
        "sem_setup": 0,
        "forca": 0,
        "continuidade": 0
    }

    for i in range(60, len(df)-2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 17:
            continue

        sub = df.iloc[:i]

        sinal, erros = analisar(sub)

        if sinal == "AGUARDAR":

            erros_stats["sem_setup"] += 1

            if "Sem força" in str(erros):
                erros_stats["forca"] += 1

            continue

        entrada = df["close"].iloc[i+1]
        saida = df["close"].iloc[i+2]

        trade = {
            "data": str(df["datetime"].iloc[i]),
            "tipo": sinal,
            "entrada": entrada,
            "saida": saida,
            "erros": erros
        }

        if sinal == "COMPRA":
            if saida > entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"

        elif sinal == "VENDA":
            if saida < entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"

        log.append(trade)

    return wins, loss, log, erros_stats

# ======================
# SELETOR DE ATIVOS
# ======================

def score(df):
    return (df["close"].iloc[-1] - df["close"].iloc[-10])

scores = []

for ativo in ATIVOS:
    df_temp = pegar_dados(ativo)
    scores.append({
        "ativo": ativo,
        "score": score(df_temp),
        "df": df_temp
    })

melhor = max(scores, key=lambda x: x["score"])
df = melhor["df"]

# ======================
# PAINEL
# ======================

st.subheader("📊 Ranking de Ativos")

for s in scores:
    st.write(f"{s['ativo']} → Score: {round(s['score'],5)}")

st.success(f"🔥 ATIVO ESCOLHIDO: {melhor['ativo']}")

sinal, erros = analisar(df)

st.subheader("Sinal Atual")
st.write(sinal)
st.write(erros)

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest PRO"):

    wins, loss, log, erros_stats = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("RESULTADO")

    st.write("Wins:", wins)
    st.write("Loss:", loss)
    st.write("Assertividade:", round(taxa, 2))

    st.subheader("ERROS")

    st.write(erros_stats)

    st.subheader("LOG DETALHADO")

    for t in log:
        st.write(t)

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

fig.update_layout(template="plotly_dark", height=600)

st.plotly_chart(fig, use_container_width=True)
