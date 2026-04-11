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

ATIVO = "USD/JPY"

# ======================
# BOTÃO ATUALIZAR
# ======================

if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
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
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    if df["close"].iloc[-1] > df["EMA21"].iloc[-1]:
        return "ALTA"
    elif df["close"].iloc[-1] < df["EMA21"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# ESTRATÉGIA (NÃO MEXIDA)
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    preco = df["close"].iloc[-1]
    erros = []

    i = len(df) - 1

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        range_total = df["high"].iloc[i] - df["low"].iloc[i]

        if range_total == 0:
            return False

        return (corpo / range_total) > 0.6

    # ======================
    # FILTRO LATERAL
    # ======================

    cruzamentos = 0
    for j in range(i-10, i):
        if (df["EMA5"].iloc[j] > df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["EMA5"].iloc[j] < df["EMA21"].iloc[j] and df["EMA5"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    if cruzamentos >= 3:
        erros.append("Mercado lateral")
        agora = datetime.datetime.now()
        return "AGUARDAR", preco, agora, agora, erros

    # ======================
    # CRUZAMENTO
    # ======================

    if i > 3:

        dist_antes = abs(df["EMA5"].iloc[i-2] - df["EMA21"].iloc[i-2])

        # COMPRA
        if df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]:

            if dist_antes < 0.0002:
                erros.append("Cruzamento muito próximo")
            else:

                if df["EMA21"].iloc[i] <= df["EMA21"].iloc[i-1]:
                    erros.append("M21 sem inclinação alta")
                else:

                    if df["close"].iloc[i-1] > df["open"].iloc[i-1] and vela_forte(i-1):

                        if df["high"].iloc[i] > df["high"].iloc[i-1] and df["close"].iloc[i] > df["open"].iloc[i]:

                            entrada = df["datetime"].iloc[i]
                            saida = entrada + datetime.timedelta(minutes=5)

                            return "COMPRA", preco, entrada, saida, erros
                        else:
                            erros.append("Sem continuidade compra")
                    else:
                        erros.append("Sem força compra")

        # VENDA
        if df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]:

            if dist_antes < 0.0002:
                erros.append("Cruzamento muito próximo")
            else:

                if df["EMA21"].iloc[i] >= df["EMA21"].iloc[i-1]:
                    erros.append("M21 sem inclinação baixa")
                else:

                    if df["close"].iloc[i-1] < df["open"].iloc[i-1] and vela_forte(i-1):

                        if df["low"].iloc[i] < df["low"].iloc[i-1] and df["close"].iloc[i] < df["open"].iloc[i]:

                            entrada = df["datetime"].iloc[i]
                            saida = entrada + datetime.timedelta(minutes=5)

                            return "VENDA", preco, entrada, saida, erros
                        else:
                            erros.append("Sem continuidade venda")
                    else:
                        erros.append("Sem força venda")

    erros.append("Sem cruzamento válido")

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST ANALÍTICO (NOVO)
# ======================

def backtest(df):

    wins = 0
    loss = 0

    log_trades = []

    motivos_bloqueio = {
        "lateral": 0,
        "cruzamento": 0,
        "forca": 0,
        "inclinacao": 0,
        "rompimento": 0
    }

    for i in range(50, len(df)-2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 17:
            continue

        sub = df.iloc[:i].copy()

        sinal, _, _, _, erros = analisar(sub)

        # ======================
        # CONTABILIZA BLOQUEIOS
        # ======================
        if sinal == "AGUARDAR":

            if "Mercado lateral" in erros:
                motivos_bloqueio["lateral"] += 1

            if "Cruzamento muito próximo" in erros:
                motivos_bloqueio["cruzamento"] += 1

            if "Sem força compra" in erros or "Sem força venda" in erros:
                motivos_bloqueio["forca"] += 1

            if "M21 sem inclinação alta" in erros or "M21 sem inclinação baixa" in erros:
                motivos_bloqueio["inclinacao"] += 1

            if "Sem continuidade compra" in erros or "Sem continuidade venda" in erros:
                motivos_bloqueio["rompimento"] += 1

            continue

        entrada = df["close"].iloc[i+1]
        saida = df["close"].iloc[i+2]

        trade = {
            "index": i,
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

        log_trades.append(trade)

    return wins, loss, log_trades, motivos_bloqueio

# ======================
# EXECUÇÃO
# ======================

df = pegar_dados()

trend = tendencia(df)
st.write("📊 Tendência:", trend)

sinal, preco, entrada, saida, erros = analisar(df)

st.metric("💰 Preço atual", preco)

if sinal == "COMPRA":
    st.success(f"🟢 COMPRA\nEntrada: {entrada.strftime('%H:%M')}\nSaída: {saida.strftime('%H:%M')}")

elif sinal == "VENDA":
    st.error(f"🔴 VENDA\nEntrada: {entrada.strftime('%H:%M')}\nSaída: {saida.strftime('%H:%M')}")

else:
    st.warning("⚪ AGUARDAR")

st.subheader("⚠️ Motivos de bloqueio atual")

for e in erros:
    st.write("-", e)

# ======================
# BACKTEST
# ======================

if st.button("📊 Rodar Backtest 30 dias (08h às 17h)"):

    wins, loss, log_trades, motivos = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("📈 RESULTADO")

    st.write("✅ Wins:", wins)
    st.write("❌ Loss:", loss)
    st.write(f"🎯 Assertividade: {taxa:.2f}%")

    st.subheader("📊 MOTIVOS DE BLOQUEIO")

    st.write(motivos)

    st.subheader("📉 LOG DETALHADO DE TRADES")

    for t in log_trades:
        st.write("----")
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

fig.update_layout(template="plotly_dark", height=500)

st.plotly_chart(fig, use_container_width=True)
