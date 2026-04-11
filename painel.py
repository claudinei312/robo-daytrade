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

st.set_page_config(page_title="Robô PRO Equilibrado", layout="wide")
st.title("🤖 Robô PRO Equilibrado + Backtest Avançado")

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
# SCORE DO ATIVO
# ======================

def score_ativo(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    i = len(df) - 1

    inclinacao = df["EMA21"].iloc[i] - df["EMA21"].iloc[i-5]

    cruzamentos = 0
    for j in range(i-10, i):
        if j <= 0:
            continue

        if (df["EMA5"].iloc[j] > df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["EMA5"].iloc[j] < df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    score = 0

    if abs(inclinacao) > 0.0006:
        score += 2
    else:
        score -= 1

    if cruzamentos <= 3:
        score += 2
    elif cruzamentos <= 5:
        score += 1
    else:
        score -= 2

    return score

# ======================
# ESTRATÉGIA PRO EQUILIBRADA
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    i = len(df) - 1
    erros = []
    bloqueios = []

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        range_total = df["high"].iloc[i] - df["low"].iloc[i]
        if range_total == 0:
            return False
        return (corpo / range_total) > 0.45  # MAIS REALISTA

    # ======================
    # FILTRO DE TENDÊNCIA (LEVE)
    # ======================

    tendencia = df["EMA21"].iloc[i] - df["EMA21"].iloc[i-5]

    # ======================
    # COMPRA
    # ======================

    if df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]:

        if tendencia > -0.0005:  # leve filtro

            if vela_forte(i-1):

                if df["high"].iloc[i] > df["high"].iloc[i-1]:

                    return "COMPRA", erros, bloqueios
                else:
                    erros.append("Sem rompimento (opcional)")

            else:
                erros.append("Sem força suficiente")

        else:
            bloqueios.append("Tendência fraca compra")

    # ======================
    # VENDA
    # ======================

    if df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]:

        if tendencia < 0.0005:

            if vela_forte(i-1):

                if df["low"].iloc[i] < df["low"].iloc[i-1]:

                    return "VENDA", erros, bloqueios
                else:
                    erros.append("Sem rompimento (opcional)")

            else:
                erros.append("Sem força suficiente")

        else:
            bloqueios.append("Tendência fraca venda")

    bloqueios.append("Sem setup")
    return "AGUARDAR", erros, bloqueios

# ======================
# BACKTEST PROFISSIONAL
# ======================

def backtest(df):

    wins = 0
    loss = 0
    log = []

    stats_erros = {
        "sem_setup": 0,
        "forca": 0,
        "rompimento": 0,
        "tendencia": 0
    }

    for i in range(60, len(df)-2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 17:
            continue

        sub = df.iloc[:i]

        sinal, erros, bloqueios = analisar(sub)

        if sinal == "AGUARDAR":

            stats_erros["sem_setup"] += 1

            if "Sem força suficiente" in erros:
                stats_erros["forca"] += 1

            if "Sem rompimento" in erros:
                stats_erros["rompimento"] += 1

            if bloqueios:
                stats_erros["tendencia"] += 1

            continue

        entrada = df["close"].iloc[i+1]
        saida = df["close"].iloc[i+2]

        trade = {
            "data": str(df["datetime"].iloc[i]),
            "tipo": sinal,
            "entrada": entrada,
            "saida": saida,
            "erros": erros + bloqueios
        }

        if sinal == "COMPRA":
            if saida > entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"

        if sinal == "VENDA":
            if saida < entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"

        log.append(trade)

    return wins, loss, log, stats_erros

# ======================
# SELETOR DE ATIVOS
# ======================

scores = []

for ativo in ATIVOS:

    df_temp = pegar_dados(ativo)
    score = score_ativo(df_temp)

    scores.append({
        "ativo": ativo,
        "score": score,
        "df": df_temp
    })

melhor = max(scores, key=lambda x: x["score"])
df = melhor["df"]

# ======================
# PAINEL
# ======================

st.subheader("📊 Ranking de Ativos")

for s in sorted(scores, key=lambda x: x["score"], reverse=True):
    st.write(f"{s['ativo']} → Score: {s['score']}")

st.success(f"🔥 ATIVO ESCOLHIDO: {melhor['ativo']}")

sinal, erros, bloqueios = analisar(df)

st.subheader("Sinal Atual")
st.write(sinal)
st.write(erros)
st.write(bloqueios)

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest PRO"):

    wins, loss, log, stats_erros = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("RESULTADO")

    st.write("Wins:", wins)
    st.write("Loss:", loss)
    st.write("Assertividade:", round(taxa,2))

    st.subheader("ERROS DETALHADOS")

    st.write(stats_erros)

    st.subheader("LOG COMPLETO")

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
