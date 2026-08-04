"""
Tekniska indikatorer: RSI, MACD, Bollinger Bands, ATR och Golden/Death Cross.
"""

import pandas as pd


def berakna_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def berakna_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_linje = ema12 - ema26
    signal_linje = macd_linje.ewm(span=9, adjust=False).mean()
    return macd_linje, signal_linje, macd_linje - signal_linje


def berakna_bollinger(close, period=20, antal_std=2):
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return sma, sma + antal_std * std, sma - antal_std * std


def berakna_atr(hist, period=14):
    high_low = hist["High"] - hist["Low"]
    high_close = (hist["High"] - hist["Close"].shift()).abs()
    low_close = (hist["Low"] - hist["Close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def golden_death_status(close):
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    if pd.isna(ma50.iloc[-1]) or pd.isna(ma200.iloc[-1]):
        return "Otillräcklig historik (behöver minst 200 dagars data)"
    return ("Golden Cross-läge (MA50 över MA200, historiskt bullish)" if ma50.iloc[-1] > ma200.iloc[-1]
            else "Death Cross-läge (MA50 under MA200, historiskt bearish)")
