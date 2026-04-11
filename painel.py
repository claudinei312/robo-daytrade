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
# TENDÊNCIA (M21)
# ======================

def tendencia(df):
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    if df["close"].iloc[-1] > df["EMA21"].iloc[-1]:
        return "ALTA"
    elif df["close"].iloc[-1] < df["EMA21"].iloc[-1]:
        return "BAIXA"
    return "LATERAL"

# ======================
# ESTRATÉGIA
# ======================

def analisar(df):

    df["EMA5"] = EMAIndicator(df["close"],5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"],21).ema_indicator()

    preco = df["close"].iloc[-1]
    trend = tendencia(df)

    erros = []
    i = len(df) - 1

    # ======================
    # VELA FORTE
    # ======================

    def vela_forte(i):
        corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
        media = (
            abs(df["close"].iloc[i-1] - df["open"].iloc[i-1]) +
            abs(df["close"].iloc[i-2] - df["open"].iloc[i-2]) +
            abs(df["close"].iloc[i-3] - df["open"].iloc[i-3])
        ) / 3
        return corpo > media

    # ======================
    # TOQUE NA M21
    # ======================

    def tocou_m21(i):
        return df["low"].iloc[i] <= df["EMA21"].iloc[i] <= df["high"].iloc[i]

    # ======================
    # FILTRO LATERAL
    # ======================

    cruzamentos = 0
    for j in range(i-10, i):
        if (df["close"].iloc[j] > df["EMA21"].iloc[j] and df["close"].iloc[j-1] < df["EMA21"].iloc[j-1]) or \
           (df["close"].iloc[j] < df["EMA21"].iloc[j] and df["close"].iloc[j-1] > df["EMA21"].iloc[j-1]):
            cruzamentos += 1

    if cruzamentos >= 3:
        erros.append("Mercado lateral")
        agora = datetime.datetime.now()
        return "AGUARDAR", preco, agora, agora, erros

    # ======================
    # PULLBACK COM CONFIRMAÇÃO
    # ======================

    if i > 1:

        # COMPRA
        if trend == "ALTA" and tocou_m21(i-1):
            if df["close"].iloc[i-1] > df["open"].iloc[i-1] and vela_forte(i-1):
                if df["high"].iloc[i] > df["high"].iloc[i-1]:
                    entrada = df["datetime"].iloc[i]
                    saida = entrada + datetime.timedelta(minutes=5)
                    return "COMPRA", preco, entrada, saida, erros
                else:
                    erros.append("Sem rompimento compra")

        # VENDA
        if trend == "BAIXA" and tocou_m21(i-1):
            if df["close"].iloc[i-1] < df["open"].iloc[i-1] and vela_forte(i-1):
                if df["low"].iloc[i] < df["low"].iloc[i-1]:
                    entrada = df["datetime"].iloc[i]
                    saida = entrada + datetime.timedelta(minutes=5)
                    return "VENDA", preco, entrada, saida, erros
                else:
                    erros.append("Sem rompimento venda")

    # ======================
    # CRUZAMENTO COM CONFIRMAÇÃO
    # ======================

    if i > 2:

        # COMPRA
        if df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]:
            if df["close"].iloc[i-1] > df["open"].iloc[i-1] and vela_forte(i-1):
                if df["high"].iloc[i] > df["high"].iloc[i-1]:
                    entrada = df["datetime"].iloc[i]
                    saida = entrada + datetime.timedelta(minutes=5)
                    return "COMPRA", preco, entrada, saida, erros
                else:
                    erros.append("Cruzamento sem rompimento")

        # VENDA
        if df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]:
            if df["close"].iloc[i-1] < df["open"].iloc[i-1] and vela_forte(i-1):
                if df["low"].iloc[i] < df["low"].iloc[i-1]:
                    entrada = df["datetime"].iloc[i]
                    saida = entrada + datetime.timedelta(minutes=5)
                    return "VENDA", preco, entrada, saida, erros
                else:
                    erros.append("Cruzamento sem rompimento")

    erros.append("Sem entrada válida")

    agora = datetime.datetime.now()
    entrada = agora + datetime.timedelta(minutes=5)
    saida = entrada + datetime.timedelta(minutes=5)

    return "AGUARDAR", preco, entrada, saida, erros

# ======================
# BACKTEST
# ======================

def backtest(df):

    wins = 0
    loss = 0
    erros_log = []

    for i in range(50, len(df)-2):

        hora = df["datetime"].iloc[i].hour

        if hora < 8 or hora > 12:
            continue

        sub = df.iloc[:i].copy()

        sinal, _, _, _, erros = analisar(sub)

        if sinal == "AGUARDAR":
            continue

        entrada = df["close"].iloc[i+1]
        saida = df["close"].iloc[i+2]

        if sinal == "COMPRA":
            if saida > entrada:
                wins += 1
            else:
                loss += 1
                erros_log.extend(erros if erros else ["Entrada fraca compra"])

        elif sinal == "VENDA":
            if saida < entrada:
                wins += 1
            else:
                loss += 1
                erros_log.extend(erros if erros else ["Entrada fraca venda"])

    return wins, loss, erros_log

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

st.subheader("⚠️ Motivos para não entrar forte")

for e in erros:
    st.write("-", e)

if st.button("📊 Rodar Backtest 30 dias (08h às 12h)"):

    wins, loss, erros_log = backtest(df)

    total = wins + loss
    taxa = (wins / total * 100) if total > 0 else 0

    st.subheader("📈 Resultado")

    st.write("✅ Wins:", wins)
    st.write("❌ Loss:", loss)
    st.write(f"🎯 Assertividade: {taxa:.2f}%")

    st.subheader("⚠️ Principais erros")

    for e in set(erros_log):
        st.write("-", e)

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
