"""
Riskmått: volatilitet, Sharpe-kvot, max drawdown och beta.
"""

import pandas as pd


def berakna_volatilitet(close):
    r = close.pct_change(fill_method=None).dropna()
    return r.std() * (252 ** 0.5) * 100 if len(r) > 1 else None


def berakna_sharpe(close, riskfri_ranta=0.02):
    r = close.pct_change(fill_method=None).dropna()
    if len(r) < 2 or r.std() == 0:
        return None
    return (r.mean() * 252 - riskfri_ranta) / (r.std() * (252 ** 0.5))


def berakna_max_drawdown(close):
    topp = close.cummax()
    return ((close - topp) / topp).min() * 100


def berakna_beta(aktie_close, index_close):
    gemensamt = pd.concat(
        [aktie_close.pct_change(fill_method=None), index_close.pct_change(fill_method=None)],
        axis=1, join="inner",
    ).dropna()
    if len(gemensamt) < 30:
        return None
    varians = gemensamt.iloc[:, 1].var()
    if varians == 0:
        return None
    return gemensamt.iloc[:, 0].cov(gemensamt.iloc[:, 1]) / varians
