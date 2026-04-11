import streamlit as st
from twelvedata import TDClient
import pandas as pd
import plotly.graph_objects as go
from ta.trend import EMAIndicator

# ======================
# CONFIG
# ======================

API_KEY = "4b17399dcf214533abd7d72ea416f1df"
td = TDClient(apikey=API_KEY)

st.set_page_config(page_title="Scanner Diagnóstico PRO", layout="wide")
st.title("📊 EMA Scanner PRO + Diagnóstico de Loss")

ATIVOS = ["USD/JPY", "EUR/USD", "GBP/USD"]

# ======================
# DADOS
# ======================

@st.cache_data(ttl=120)
def pegar_dados(ativo):

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=1500
    ).as_pandas()

    df = df[::-1].reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"])

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df.dropna()

# ======================
# VELA FORTE
# ======================

def vela_forte(df, i):
    corpo = abs(df["close"].iloc[i] - df["open"].iloc[i])
    range_total = df["high"].iloc[i] - df["low"].iloc[i]
    if range_total == 0:
        return False
    return (corpo / range_total) >= 0.5

# ======================
# SCANNER COM DIAGNÓSTICO
# ======================

def scanner(df):

    df["EMA5"] = EMAIndicator(df["close"], 5).ema_indicator()
    df["EMA21"] = EMAIndicator(df["close"], 21).ema_indicator()

    wins = 0
    loss = 0

    trades = []
    erros_lista = []

    for i in range(50, len(df) - 3):

        # ======================
        # COMPRA
        # ======================

        cruz_compra = (
            df["EMA5"].iloc[i-2] < df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] > df["EMA21"].iloc[i-1]
        )

        if cruz_compra:

            if not vela_forte(df, i-1):
                erros_lista.append("COMPRA: sem força")
                continue

            entrada = df["close"].iloc[i]
            saida = df["close"].iloc[i+2]

            trade = {
                "tipo": "COMPRA",
                "entrada": entrada,
                "saida": saida
            }

            if saida > entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"
                erros_lista.append("COMPRA: movimento insuficiente")

            trades.append(trade)

        # ======================
        # VENDA
        # ======================

        cruz_venda = (
            df["EMA5"].iloc[i-2] > df["EMA21"].iloc[i-2] and
            df["EMA5"].iloc[i-1] < df["EMA21"].iloc[i-1]
        )

        if cruz_venda:

            if not vela_forte(df, i-1):
                erros_lista.append("VENDA: sem força")
                continue

            entrada = df["close"].iloc[i]
            saida = df["close"].iloc[i+2]

            trade = {
                "tipo": "VENDA",
                "entrada": entrada,
                "saida": saida
            }

            if saida < entrada:
                wins += 1
                trade["resultado"] = "WIN"
            else:
                loss += 1
                trade["resultado"] = "LOSS"
                erros_lista.append("VENDA: movimento insuficiente")

            trades.append(trade)

    return wins, loss, trades, erros_lista

# ======================
# ANALISE POR ATIVO
# ======================

resultados = []

for ativo in ATIVOS:

    df = pegar_dados(ativo)
    w, l, trades, erros = scanner(df)

    total = w + l
    acc = (w / total * 100) if total > 0 else 0

    resultados.append({
        "ativo": ativo,
        "wins": w,
        "loss": l,
        "acc": acc,
        "erros": erros,
        "df": df,
        "trades": trades
    })

melhor = max(resultados, key=lambda x: x["acc"])

# ======================
# PAINEL
# ======================

st.subheader("📊 Ranking de Ativos")

for r in resultados:

    st.write(f"""
### {r['ativo']}
Wins: {r['wins']} | Loss: {r['loss']} | Assertividade: {round(r['acc'],2)}%

Erros principais:
{list(set(r['erros']))}
""")

st.success(f"🔥 Melhor ativo: {melhor['ativo']}")

# ======================
# RESULTADO ATUAL
# ======================

w, l, trades, erros = scanner(melhor["df"])

total = w + l
acc = (w / total * 100) if total > 0 else 0

st.subheader("📈 RESULTADO ATUAL")

st.write("Wins:", w)
st.write("Loss:", l)
st.write("Assertividade:", round(acc,2))

st.subheader("⚠️ PRINCIPAIS ERROS (GERAL)")

st.write(list(set(erros)))

# ======================
# LOG DE TRADES
# ======================

st.subheader("📜 ÚLTIMOS TRADES")

for t in trades[-20:]:
    st.write(t)

# ======================
# GRÁFICO
# ======================

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=melhor["df"]["datetime"],
    open=melhor["df"]["open"],
    high=melhor["df"]["high"],
    low=melhor["df"]["low"],
    close=melhor["df"]["close"]
))

fig.update_layout(template="plotly_dark", height=600)

st.plotly_chart(fig, use_container_width=True)
