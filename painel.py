# ===== INSTALAR =====
# pip install streamlit twelvedata ta pandas requests

import streamlit as st
from twelvedata import TDClient
import pandas as pd
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from datetime import datetime

# ===== CONFIG =====
API_KEY = "4b17399dcf214533abd7d72ea416f1df"
ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

td = TDClient(apikey=API_KEY)

# ===== FUNÇÃO DADOS =====
def pegar_dados(ativo):
    try:
        ts = td.time_series(symbol=ativo, interval="5min", outputsize=100).as_pandas()
        ts = ts[::-1].reset_index(drop=True)

        for col in ['open','high','low','close']:
            ts[col] = pd.to_numeric(ts[col], errors='coerce')

        return ts.dropna()
    except:
        return None

# ===== ANÁLISE =====
def analisar(data):
    data['MA9'] = SMAIndicator(data['close'], 9).sma_indicator()
    data['MA21'] = SMAIndicator(data['close'], 21).sma_indicator()
    data['MA200'] = SMAIndicator(data['close'], 200).sma_indicator()
    data['RSI'] = RSIIndicator(data['close'], 14).rsi()
    data['ATR'] = AverageTrueRange(data['high'], data['low'], data['close'], 14).average_true_range()

    preco = data['close'].iloc[-1]
    ma9 = data['MA9'].iloc[-1]
    ma21 = data['MA21'].iloc[-1]
    ma200 = data['MA200'].iloc[-1]
    rsi = data['RSI'].iloc[-1]

    suporte = data['low'].rolling(20).min().iloc[-1]
    resistencia = data['high'].rolling(20).max().iloc[-1]

    # lógica simplificada visual
    if preco > ma200 and ma9 > ma21 and rsi > 60:
        return "COMPRA", preco
    elif preco < ma200 and ma9 < ma21 and rsi < 40:
        return "VENDA", preco
    else:
        return "AGUARDAR", preco

# ===== VISUAL =====
st.set_page_config(layout="wide")
st.title("📊 ROBÔ DAY TRADE - PAINEL AO VIVO")

colunas = st.columns(3)

for i, ativo in enumerate(ativos):
    with colunas[i]:
        st.subheader(f"📈 {ativo}")

        data = pegar_dados(ativo)

        if data is not None:
            sinal, preco = analisar(data)

            # cores
            if sinal == "COMPRA":
                cor = "🟢"
            elif sinal == "VENDA":
                cor = "🔴"
            else:
                cor = "⚪"

            st.metric("Preço", f"{preco:.5f}")
            st.markdown(f"### {cor} {sinal}")

            # gráfico simples
            st.line_chart(data['close'])

        else:
            st.error("Erro ao carregar dados")

st.write("🕒 Atualizado em:", datetime.now())
