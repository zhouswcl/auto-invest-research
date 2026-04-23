"""
===========================================================
  投研分析模块
  包含：技术指标计算、基本面分析、综合研判
===========================================================
"""
import numpy as np
import pandas as pd
from utils import logger, safe_float, pct_change_str


# ======================== 技术指标 ========================

def compute_ma(series, periods=(5, 10, 20, 60)):
    """计算移动平均线"""
    result = {}
    for p in periods:
        col_name = f"MA{p}"
        result[col_name] = series.rolling(window=p, min_periods=1).mean().round(2)
    return result


def compute_macd(series, fast=12, slow=26, signal=9):
    """计算 MACD 指标"""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    dif = (ema_fast - ema_slow).round(4)
    dea = dif.ewm(span=signal, adjust=False).mean().round(4)
    histogram = (2 * (dif - dea)).round(4)
    return dif, dea, histogram


def compute_kdj(high, low, close, n=9, m1=3, m2=3):
    """计算 KDJ 指标"""
    lowest_low = low.rolling(window=n, min_periods=1).min()
    highest_high = high.rolling(window=n, min_periods=1).max()
    rsv = ((close - lowest_low) / (highest_high - lowest_low) * 100).fillna(50)
    k = rsv.ewm(com=m1 - 1, adjust=False).mean().round(2)
    d = k.ewm(com=m2 - 1, adjust=False).mean().round(2)
    j = (3 * k - 2 * d).round(2)
    return k, d, j


def compute_rsi(series, period=14):
    """计算 RSI 指标"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = (100 - 100 / (1 + rs)).round(2)
    return rsi


def compute_boll(series, period=20, std_dev=2):
    """计算布林带"""
    mid = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std()
    upper = (mid + std_dev * std).round(2)
    lower = (mid - std_dev * std).round(2)
    return upper, mid, lower


# ======================== 信号判断 ========================

def judge_ma_signal(close, mas):
    """
    判断均线信号
    返回: list of str, 如 ['MA5上穿MA10(金叉)', '价格站上MA20']
    """
    signals = []
    if len(close) < 2:
        return signals

    price = close.iloc[-1]
    prev_price = close.iloc[-2]

    # 价格与均线关系
    for name, ma_series in mas.items():
        if len(ma_series) < 1:
            continue
        ma_val = ma_series.iloc[-1]
        if prev_price < ma_val and price >= ma_val:
            signals.append(f"价格上穿{name}（站上{name}）")
        elif prev_price > ma_val and price <= ma_val:
            signals.append(f"价格下穿{name}（跌破{name}）")

    # 均线交叉
    ma_keys = list(mas.keys())
    for i in range(len(ma_keys) - 1):
        short_name = ma_keys[i]
        long_name = ma_keys[i + 1]
        short_s = mas[short_name]
        long_s = mas[long_name]
        if len(short_s) < 2 or len(long_s) < 2:
            continue
        if short_s.iloc[-2] <= long_s.iloc[-2] and short_s.iloc[-1] > long_s.iloc[-1]:
            signals.append(f"{short_name}上穿{long_name}（金叉）")
        elif short_s.iloc[-2] >= long_s.iloc[-2] and short_s.iloc[-1] < long_s.iloc[-1]:
            signals.append(f"{short_name}下穿{long_name}（死叉）")

    return signals


def judge_macd_signal(dif, dea, histogram):
    """判断 MACD 信号"""
    signals = []
    if len(histogram) < 2:
        return signals
    # 金叉/死叉
    if histogram.iloc[-2] <= 0 and histogram.iloc[-1] > 0:
        signals.append("MACD金叉")
    elif histogram.iloc[-2] >= 0 and histogram.iloc[-1] < 0:
        signals.append("MACD死叉")
    # 红绿柱变化
    if histogram.iloc[-1] > 0 and histogram.iloc[-1] > histogram.iloc[-2]:
        signals.append("MACD红柱放大")
    elif histogram.iloc[-1] > 0 and histogram.iloc[-1] < histogram.iloc[-2]:
        signals.append("MACD红柱缩短")
    elif histogram.iloc[-1] < 0 and abs(histogram.iloc[-1]) > abs(histogram.iloc[-2]):
        signals.append("MACD绿柱放大")
    elif histogram.iloc[-1] < 0 and abs(histogram.iloc[-1]) < abs(histogram.iloc[-2]):
        signals.append("MACD绿柱缩短")
    return signals


def judge_kdj_signal(k, d, j):
    """判断 KDJ 信号"""
    signals = []
    if len(k) < 2:
        return signals
    if k.iloc[-2] < d.iloc[-2] and k.iloc[-1] > d.iloc[-1]:
        signals.append("KDJ金叉")
    elif k.iloc[-2] > d.iloc[-2] and k.iloc[-1] < d.iloc[-1]:
        signals.append("KDJ死叉")
    # 超买超卖
    if k.iloc[-1] > 80:
        signals.append("KDJ进入超买区间")
    elif k.iloc[-1] < 20:
        signals.append("KDJ进入超卖区间")
    return signals


def judge_volume_signal(volume_series, latest_volume_ratio=0):
    """判断成交量信号"""
    signals = []
    if len(volume_series) < 5:
        return signals
    avg_vol = volume_series.tail(20).mean()
    if avg_vol > 0:
        ratio = volume_series.iloc[-1] / avg_vol
        if ratio >= 2.0:
            signals.append(f"成交量显著放量（为20日均量{ratio:.1f}倍）")
        elif ratio >= 1.5:
            signals.append(f"成交量温和放量（为20日均量{ratio:.1f}倍）")
        elif ratio <= 0.5:
            signals.append(f"成交量显著缩量（为20日均量{ratio:.1f}倍）")
    if latest_volume_ratio >= 2.5:
        signals.append(f"量比高达{latest_volume_ratio:.1f}，成交活跃")
    return signals


# ======================== 综合技术分析 ========================

def analyze_technical(history_df, realtime_info=None):
    """
    对个股进行综合技术分析
    history_df: 历史K线 DataFrame
    realtime_info: 实时行情 dict（可选）
    返回: dict
    """
    if history_df is None or history_df.empty or len(history_df) < 5:
        return {"status": "数据不足", "signals": []}

    # 列名映射（兼容不同版本 AkShare）
    col_map = {}
    for df_col, std_name in [
        ("收盘", "close"), ("日期", "date"), ("最高", "high"),
        ("最低", "low"), ("成交量", "volume"), ("开盘", "open"),
        ("涨跌幅", "change_pct"), ("换手率", "turnover"),
    ]:
        for c in history_df.columns:
            if df_col in c:
                col_map[c] = std_name
                break
    df = history_df.rename(columns=col_map)

    close = pd.to_numeric(df["close"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")

    # 计算指标
    mas = compute_ma(close)
    dif, dea, hist = compute_macd(close)
    k, d, j = compute_kdj(high, low, close)
    rsi = compute_rsi(close)
    upper, mid, lower = compute_boll(close)

    # 判断信号
    all_signals = []
    all_signals.extend(judge_ma_signal(close, mas))
    all_signals.extend(judge_macd_signal(dif, dea, hist))
    all_signals.extend(judge_kdj_signal(k, d, j))
    vol_ratio = safe_float(realtime_info.get("volume_ratio", 0)) if realtime_info else 0
    all_signals.extend(judge_volume_signal(volume, vol_ratio))

    # 趋势判断
    price = close.iloc[-1]
    ma20 = mas["MA20"].iloc[-1] if "MA20" in mas else price
    ma60 = mas["MA60"].iloc[-1] if "MA60" in mas else price
    if price > ma20 > ma60:
        trend = "多头排列（偏多）"
    elif price < ma20 < ma60:
        trend = "空头排列（偏空）"
    else:
        trend = "趋势不明/震荡"

    # 支撑位与压力位
    support = round(lower.iloc[-1], 2) if len(lower) > 0 else price * 0.97
    resistance = round(upper.iloc[-1], 2) if len(upper) > 0 else price * 1.03

    return {
        "status": "OK",
        "trend": trend,
        "price": price,
        "ma5": round(mas["MA5"].iloc[-1], 2),
        "ma10": round(mas["MA10"].iloc[-1], 2),
        "ma20": round(mas["MA20"].iloc[-1], 2) if "MA20" in mas else None,
        "ma60": round(mas["MA60"].iloc[-1], 2) if "MA60" in mas else None,
        "macd_dif": round(dif.iloc[-1], 4) if len(dif) > 0 else 0,
        "macd_dea": round(dea.iloc[-1], 4) if len(dea) > 0 else 0,
        "macd_hist": round(hist.iloc[-1], 4) if len(hist) > 0 else 0,
        "kdj_k": round(k.iloc[-1], 2) if len(k) > 0 else 50,
        "kdj_d": round(d.iloc[-1], 2) if len(d) > 0 else 50,
        "kdj_j": round(j.iloc[-1], 2) if len(j) > 0 else 50,
        "rsi": round(rsi.iloc[-1], 2) if len(rsi) > 0 else 50,
        "boll_upper": support,
        "boll_lower": resistance,
        "support": support,
        "resistance": resistance,
        "signals": all_signals,
        "avg_volume_20": round(volume.tail(20).mean(), 0),
    }


# ======================== 综合投研分析 ========================

def comprehensive_stock_analysis(code, name, history_df, realtime_info, financial_data, fund_flow):
    """
    对单个股票进行综合分析（技术面 + 基本面 + 资金面）
    返回: dict
    """
    tech = analyze_technical(history_df, realtime_info)

    # 基本面概要
    fundamental_summary = ""
    if financial_data:
        parts = []
        if financial_data.get("roe") and financial_data["roe"] != 0:
            parts.append(f"ROE {financial_data['roe']:.1f}%")
        if financial_data.get("gross_margin") and financial_data["gross_margin"] != 0:
            parts.append(f"毛利率 {financial_data['gross_margin']:.1f}%")
        if financial_data.get("eps") and financial_data["eps"] != 0:
            parts.append(f"EPS {financial_data['eps']:.2f}")
        if parts:
            fundamental_summary = "，".join(parts)

    # 资金面概要
    fund_summary = ""
    if fund_flow:
        main_in = fund_flow.get("main_net_inflow", 0)
        if main_in > 0:
            fund_summary = f"主力净流入 {main_in / 1e8:.2f} 亿"
        else:
            fund_summary = f"主力净流出 {abs(main_in) / 1e8:.2f} 亿"

    # 综合评级（简易）
    score = 0
    reasons = []
    if tech["trend"] == "多头排列（偏多）":
        score += 2
        reasons.append("均线多头排列")
    if tech["rsi"] < 30:
        score += 2
        reasons.append("RSI超卖")
    elif tech["rsi"] > 70:
        score -= 2
        reasons.append("RSI超买")
    for sig in tech.get("signals", []):
        if "金叉" in sig:
            score += 1
            reasons.append(sig)
        elif "死叉" in sig:
            score -= 1
            reasons.append(sig)

    if score >= 3:
        rating = "🌟 偏多"
    elif score >= 1:
        rating = "📊 中性偏多"
    elif score <= -3:
        rating = "⚠️ 偏空"
    elif score <= -1:
        rating = "📉 中性偏空"
    else:
        rating = "➡️ 中性"

    return {
        "code": code,
        "name": name,
        "price": tech.get("price", 0),
        "change_pct": safe_float(realtime_info.get("change_pct", 0)),
        "trend": tech.get("trend", ""),
        "rating": rating,
        "score": score,
        "signals": tech.get("signals", []),
        "fundamental": fundamental_summary,
        "fund_flow": fund_summary,
        "support": tech.get("support", 0),
        "resistance": tech.get("resistance", 0),
        "raw_tech": tech,
        "raw_fundamental": financial_data,
    }
