import streamlit as st
from twelvedata import TDClient
import pandas as pd
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from datetime import datetime
import time

# ===== CONFIG =====
try:
    API_KEY = st.secrets["API_KEY"]
except:
    API_KEY = "4b17399dcf214533abd7d72ea416f1df"

ativos = ["EUR/USD:FX", "GBP/USD:FX", "USD/JPY:FX"]

td = TDClient(apikey=API_KEY)

st.set_page_config(layout="wide")
st.title("📊 ROBÔ DAY TRADE - PAINEL PROFISSIONAL")

rodando = st.toggle("🚀 Ativar Robô", value=True)

if not rodando:
    st.warning("Robô desligado")
    st.stop()

# ===== CACHE (ESSENCIAL) =====
@st.cache_data(ttl=240)  # 4 minutos (ideal para M5)
def pegar_dados(ativo):
    try:
        ts = td.time_series(symbol=ativo, interval="5min", outputsize=100).as_pandas()
        ts = ts[::-1].reset_index(drop=True)

        for col in ['open','high','low','close']:
            ts[col] = pd.to_numeric(ts[col], errors='coerce')

        return ts.dropna()
    except Exception as e:
        st.error(f"Erro {ativo}: {e}")
        return None

# ===== FILTRO NOTÍCIAS =====
def evitar_noticias():
    agora = datetime.now()
    if (agora.hour == 9 and agora.minute >= 25) or (agora.hour == 10 and agora.minute <= 5):
        return True
    return False

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
    atr = data['ATR'].iloc[-1]

    suporte = data['low'].rolling(20).min().iloc[-1]
    resistencia = data['high'].rolling(20).max().iloc[-1]

    candle = data.iloc[-1]
    corpo = abs(candle['close'] - candle['open'])
    pavio_inf = candle['open'] - candle['low']
    pavio_sup = candle['high'] - candle['open']

    rejeicao_compra = pavio_inf > corpo * 2
    rejeicao_venda = pavio_sup > corpo * 2

    lateral = abs(ma9 - ma21) < 0.0002

    # filtros
    if evitar_noticias():
        return "AGUARDAR", preco, 0, 0

    if atr < 0.0003 or atr > 0.003:
        return "AGUARDAR", preco, 0, 0

    # POTENCIAL
    if preco > ma200 and ma9 > ma21 and rsi > 55 and not lateral:
        return "COMPRA_POTENCIAL", preco, 0, 0

    if preco < ma200 and ma9 < ma21 and rsi < 45 and not lateral:
        return "VENDA_POTENCIAL", preco, 0, 0

    # CONFIRMADO
    if (
        preco > ma200 and
        ma9 > ma21 and
        rsi > 55 and
        preco <= suporte * 1.002 and
        rejeicao_compra and
        not lateral
    ):
        stop = suporte
        alvo = preco + (preco - stop) * 2
        return "COMPRA", preco, stop, alvo

    if (
        preco < ma200 and
        ma9 < ma21 and
        rsi < 45 and
        preco >= resistencia * 0.998 and
        rejeicao_venda and
        not lateral
    ):
        stop = resistencia
        alvo = preco - (stop - preco) * 2
        return "VENDA", preco, stop, alvo

    return "AGUARDAR", preco, 0, 0

# ===== PAINEL =====
colunas = st.columns(3)

for i, ativo in enumerate(ativos):
    with colunas[i]:
        st.subheader(f"📈 {ativo}")

        data = pegar_dados(ativo)

        if data is not None:
            sinal, preco, stop, alvo = analisar(data)

            if "COMPRA" in sinal:
                cor = "🟢"
            elif "VENDA" in sinal:
                cor = "🔴"
            else:
                cor = "⚪"

            st.metric("💰 Preço", f"{preco:.5f}")

            if "POTENCIAL" in sinal:
                st.warning(f"{cor} {sinal.replace('_',' ')} ⚠️")
            elif sinal in ["COMPRA","VENDA"]:
                st.success(f"{cor} {sinal} 🚨")
                st.write(f"🛑 Stop: {stop:.5f}")
                st.write(f"🎯 Alvo: {alvo:.5f}")
            else:
                st.info("⚪ AGUARDAR")

            st.line_chart(data['close'])

        else:
            st.error("Erro ao carregar")

# ===== INFO =====
agora = datetime.now()
st.write("🕒 Atualizado:", agora.strftime("%H:%M:%S"))

# ===== ATUALIZAÇÃO CONTROLADA =====
st.info("🔄 Atualização automática a cada 60 segundos (economia de API)")
time.sleep(60)
st.rerun()
