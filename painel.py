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

st.set_page_config(page_title="Robô apenas", layout="wide")
st.title("🤖 Robô apenas")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):
    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=2000
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
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    if df["close"].iloc[-1] > df["EMA21"].iloc[-1]:
        return "ALTA"
    elif df["close"].iloc[-1] < df["EMA21"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# SUA ESTRATÉGIA (NÃO ALTERADA)
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    preco = df["close"].iloc[-1]
    erros = []

    i = len(df) - 1

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        rng = df["high"].iloc[i] - df["low"].iloc[i]
        if rng == 0:
            return False
        return (corpo / rng) > 0.6

    cruzamentos = 0
    for j in range(i-10, i):
        if (df["EMA5"].iloc[j] > df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["EMA5"].iloc[j] < df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    if cruzamentos >= 3:
        erros.append("Mercado lateral")
        agora = datetime.datetime.now()
        return "AGUARDAR", preco, agora, agora, erros

    if i > 3:

        dist_antes = abs(df["EMA5"].iloc[i-2] - df["EMA21"].iloc[i-2])

        # COMPRA
        if df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]:

            if dist_antes >= 0.0002:

                if df["EMA21"].iloc[i] > df["EMA21"].iloc[i-1]:

                    if df["close"].iloc[i-1] > df["open"].iloc[i-1] and vela_forte(i-1):

                        entrada = df["datetime"].iloc[i]
                        saida = entrada + datetime.timedelta(minutes=5)

                        return "COMPRA", preco, entrada, saida, erros

        # VENDA
        if df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]:

            if dist_antes >= 0.0002:

                if df["EMA21"].iloc[i] < df["EMA21"].iloc[i-1]:

                    if df["close"].iloc[i-1] < df["open"].iloc[i-1] and vela_forte(i-1):

                        entrada = df["datetime"].iloc[i]
                        saida = entrada + datetime.timedelta(minutes=5)

                        return "VENDA", preco, entrada, saida, erros

    erros.append("Sem cruzamento válido")
    agora = datetime.datetime.now()

    return "AGUARDAR", preco, agora, agora, erros

# ======================
# BACKTEST PROFISSIONAL (NOVO)
# ======================

def backtest_real(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    wins = 0
    loss = 0
    log = []

    SL = 0.0008
    TP = 0.0012

    for i in range(100, len(df)-10):

        hora = df["datetime"].iloc[i].hour

        if not (8 <= hora <= 11 or 13 <= hora <= 15):
            continue

        sub = df.iloc[:i]

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entry = df["close"].iloc[i]

        direction = sinal

        result = None

        for j in range(i+1, i+10):

            if direction == "COMPRA":

                if df["low"].iloc[j] <= entry * (1 - SL):
                    result = "LOSS"
                    break

                if df["high"].iloc[j] >= entry * (1 + TP):
                    result = "WIN"
                    break

            if direction == "VENDA":

                if df["high"].iloc[j] >= entry * (1 + SL):
                    result = "LOSS"
                    break

                if df["low"].iloc[j] <= entry * (1 - TP):
                    result = "WIN"
                    break

        if result is None:
            continue

        if result == "WIN":
            wins += 1
        else:
            loss += 1

        log.append({
            "tipo": direction,
            "resultado": result,
            "hora": df["datetime"].iloc[i]
        })

    return wins, loss, log

# ======================
# EXECUÇÃO (3 ATIVOS)
# ======================

if st.button("📊 Rodar Backtest PROFISSIONAL"):

    resultados = []

    for ativo in ATIVOS:

        df = pegar_dados(ativo)

        w, l, log = backtest_real(df)

        total = w + l
        acc = (w / total * 100) if total > 0 else 0

        resultados.append({
            "ativo": ativo,
            "wins": w,
            "loss": l,
            "acc": acc,
            "log": log,
            "df": df
        })

    melhor = max(resultados, key=lambda x: x["acc"])

    st.subheader("📊 Ranking")

    for r in resultados:
        st.write(f"""
### {r['ativo']}
Wins: {r['wins']} | Loss: {r['loss']} | Assertividade: {round(r['acc'],2)}%
""")

    st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

    w, l, log = backtest_real(melhor["df"])

    st.subheader("📈 RESULTADO FINAL")

    st.write("Wins:", w)
    st.write("Loss:", l)
    st.write("Assertividade:", round((w/(w+l))*100 if (w+l)>0 else 0,2))

    st.subheader("📜 TRADES")

    for t in log[-20:]:
        st.write(t)

# ======================
# GRÁFICO ORIGINAL (NÃO ALTERADO)
# ======================

df = pegar_dados("USD/JPY")

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
