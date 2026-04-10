# =====================================================
# 🤖 ROBÔ SNIPER PRO - AUTO OTIMIZADOR USD/JPY
# Streamlit + Backtest + Auto Optimization
# =====================================================

import streamlit as st
import pandas as pd
from twelvedata import TDClient

# =========================
# 🔐 API KEY SEGURA
# =========================

API_KEY = st.secrets["API_KEY"]

ATIVO = "USD/JPY"

CONFIG = {
    "ma_fast": 9,
    "ma_slow": 21
}

# =========================
# 📊 DADOS
# =========================

def pegar_dados(ativo):
    td = TDClient(apikey=API_KEY)

    df = td.time_series(
        symbol=ativo,
        interval="5min",
        outputsize=300
    ).as_pandas()

    df = df.sort_index()
    return df

# =========================
# 🔧 ESTRATÉGIA
# =========================

def filtrar(df):
    df = df.copy()

    df["ma_fast"] = df["close"].rolling(CONFIG["ma_fast"]).mean()
    df["ma_slow"] = df["close"].rolling(CONFIG["ma_slow"]).mean()

    df["signal"] = 0
    df.loc[df["ma_fast"] > df["ma_slow"], "signal"] = 1
    df.loc[df["ma_fast"] < df["ma_slow"], "signal"] = -1

    return df

# =========================
# 📈 BACKTEST
# =========================

def backtest(df):

    saldo = 1000
    wins = 0
    losses = 0
    trades = 0

    for i in range(1, len(df)):

        if df["signal"].iloc[i] != df["signal"].iloc[i-1]:
            trades += 1

            if df["signal"].iloc[i] == 1:
                resultado = 1 if df["close"].iloc[i] > df["close"].iloc[i-1] else -1
            else:
                resultado = 1 if df["close"].iloc[i] < df["close"].iloc[i-1] else -1

            if resultado > 0:
                saldo += 1
                wins += 1
            else:
                saldo -= 1
                losses += 1

    winrate = (wins / trades * 100) if trades > 0 else 0

    return {
        "saldo": round(saldo, 2),
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2)
    }

# =========================
# 🤖 AUTO OTIMIZAÇÃO
# =========================

def otimizar(df):

    combinacoes = [
        (5, 20),
        (7, 21),
        (9, 21),
        (10, 30)
    ]

    melhor = None
    melhor_cfg = (9, 21)

    for f, s in combinacoes:

        CONFIG["ma_fast"] = f
        CONFIG["ma_slow"] = s

        df_temp = filtrar(df)
        res = backtest(df_temp)

        if melhor is None or res["saldo"] > melhor["saldo"]:
            melhor = res
            melhor_cfg = (f, s)

    CONFIG["ma_fast"] = melhor_cfg[0]
    CONFIG["ma_slow"] = melhor_cfg[1]

    return melhor, melhor_cfg

# =========================
# 🖥️ STREAMLIT UI
# =========================

st.set_page_config(page_title="Sniper Pro USD/JPY", layout="wide")

st.title("🤖 Sniper Pro - Auto Otimizador USD/JPY")

# =========================
# 📊 DATA LOAD
# =========================

df = pegar_dados(ATIVO)

if df is None or df.empty:
    st.error("Erro ao carregar dados da API")
    st.stop()

# =========================
# 🤖 OTIMIZAÇÃO
# =========================

melhor, cfg = otimizar(df)

# =========================
# 📊 RESULTADO FINAL
# =========================

df_final = filtrar(df)
resultado = backtest(df_final)

# =========================
# 📊 PAINEL
# =========================

col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Saldo", resultado["saldo"])
col2.metric("📊 Trades", resultado["trades"])
col3.metric("🟢 Wins", resultado["wins"])
col4.metric("📈 Win Rate", f'{resultado["winrate"]}%')

st.divider()

st.subheader("⚙️ Configuração Atual (Auto Otimizada)")
st.write(CONFIG)

st.subheader("🏆 Melhor Estratégia Encontrada")
st.json(melhor)

st.subheader("📊 Resultado Atual")
st.json(resultado)

st.info("⚡ Atualização automática via GitHub Actions às 08:00")
