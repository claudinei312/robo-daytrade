import streamlit as st
from twelvedata import TDClient
import pandas as pd
import datetime
from ta.trend import EMAIndicator

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Seletor Forex", layout="wide")
st.title("🤖 Seletor Automático de Ativos Forex")

# ======================
# LISTA DE ATIVOS
# ======================

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=500
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# SCORE DE FORÇA DO ATIVO
# ======================

def score_ativo(df):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    i = len(df) - 1

    # tendência
    inclinacao = df["EMA21"].iloc[i] - df["EMA21"].iloc[i-5]

    # cruzamentos
    cruzamentos = 0
    for j in range(i-10, i):
        if j <= 0:
            continue

        if (df["EMA5"].iloc[j] > df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["EMA5"].iloc[j] < df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    # score final
    score = 0

    # tendência forte
    if abs(inclinacao) > 0.0008:
        score += 2
    else:
        score -= 1

    # mercado limpo
    if cruzamentos <= 2:
        score += 2
    elif cruzamentos <= 4:
        score += 1
    else:
        score -= 2

    # direção clara
    distancia = abs(df["EMA5"].iloc[i] - df["EMA21"].iloc[i])
    if distancia > 0.001:
        score += 1

    return score

# ======================
# ANALISAR TODOS OS ATIVOS
# ======================

resultados = []

for ativo in ATIVOS:

    df = pegar_dados(ativo)

    score = score_ativo(df)

    resultados.append({
        "ativo": ativo,
        "score": score
    })

# ordenar melhor ativo
melhor = max(resultados, key=lambda x: x["score"])

# ======================
# DISPLAY
# ======================

st.subheader("📊 Ranking de Ativos")

for r in sorted(resultados, key=lambda x: x["score"], reverse=True):
    st.write(f"{r['ativo']} → Score: {r['score']}")

st.subheader("🔥 MELHOR ATIVO AGORA")

st.success(f"""
Ativo: {melhor['ativo']}
Score: {melhor['score']}
""")

# ======================
# OPÇÃO: USAR ATIVO ESCOLHIDO NO ROBÔ
# ======================

ATIVO_ESCOLHIDO = melhor["ativo"]

st.info(f"Robô operando em: {ATIVO_ESCOLHIDO}")
