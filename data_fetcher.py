"""
===========================================================
  数据采集模块
  数据源：AkShare（免费、无需认证、覆盖全面）
  若需 Tushare 作为备选，取消相关代码注释即可
===========================================================
"""
import time
import akshare as ak
import pandas as pd
import config
from utils import logger, safe_float, safe_int, beijing_now, today_str


def _timer(func):
    """函数耗时装饰器"""
    def wrapper(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        logger.info(f"[数据] {func.__name__} 完成 ({time.time()-t0:.1f}s)")
        return result
    return wrapper


# ======================== 行情数据 ========================

@_timer
def fetch_all_realtime_quotes():
    """
    获取全部 A 股实时行情
    返回: DataFrame，列含 代码/名称/最新价/涨跌幅/成交量/成交额/换手率/量比/市盈率 等
    """
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            logger.info(f"[数据] 实时行情共 {len(df)} 条")
            return df
    except Exception as e:
        logger.error(f"[数据] 获取实时行情失败: {e}")
    return pd.DataFrame()


@_timer
def fetch_stock_pool_quotes(stock_pool):
    """
    获取股票池中各股的实时行情
    stock_pool: list of (code, name)
    返回: dict {code: {name, price, change_pct, volume, amount, turnover, volume_ratio, pe, pb, ...}}
    """
    full_df = fetch_all_realtime_quotes()
    if full_df.empty:
        logger.warning("[数据] 全量行情为空，无法筛选股票池")
        return {}

    # 尝试匹配代码列（不同版本 AkShare 列名可能不同）
    code_col = None
    for candidate in ["代码", "code", "股票代码"]:
        if candidate in full_df.columns:
            code_col = candidate
            break
    if code_col is None:
        logger.error(f"[数据] 无法识别代码列，现有列: {list(full_df.columns)}")
        return {}

    pool_codes = [item[0] for item in stock_pool]
    pool_names = {item[0]: item[1] for item in stock_pool}
    filtered = full_df[full_df[code_col].astype(str).isin(pool_codes)]

    result = {}
    for _, row in filtered.iterrows():
        code = str(row[code_col]).zfill(6)
        result[code] = {
            "code": code,
            "name": pool_names.get(code, str(row.get("名称", ""))),
            "price": safe_float(row.get("最新价")),
            "change_pct": safe_float(row.get("涨跌幅")),
            "change_amt": safe_float(row.get("涨跌额")),
            "volume": safe_float(row.get("成交量")),
            "amount": safe_float(row.get("成交额")),
            "high": safe_float(row.get("最高")),
            "low": safe_float(row.get("最低")),
            "open": safe_float(row.get("今开")),
            "pre_close": safe_float(row.get("昨收")),
            "turnover": safe_float(row.get("换手率")),
            "volume_ratio": safe_float(row.get("量比")),
            "pe_ttm": safe_float(row.get("市盈率-动态")),
            "pb": safe_float(row.get("市净率")),
            "amplitude": safe_float(row.get("振幅")),
        }
    return result


# ======================== 历史 K 线 ========================

@_timer
def fetch_stock_history(code, days=60, period="daily"):
    """
    获取个股历史 K 线数据（前复权）
    code: 6位股票代码
    days: 回溯天数
    period: daily / weekly / monthly
    返回: DataFrame [日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 涨跌幅, 换手率]
    """
    end_date = today_str().replace("-", "")
    start_date = (beijing_now() - pd.Timedelta(days=days * 2)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, period=period,
            start_date=start_date, end_date=end_date,
            adjust="qfq"
        )
        if df is not None and not df.empty:
            # 取最近 N 条
            df = df.tail(days).reset_index(drop=True)
            return df
    except Exception as e:
        logger.error(f"[数据] 获取 {code} 历史K线失败: {e}")
    return pd.DataFrame()


# ======================== 财务数据 ========================

@_timer
def fetch_financial_indicator(code):
    """
    获取个股财务分析指标（最近 4 个报告期）
    返回: dict {roe, gross_margin, net_margin, revenue_growth, ...}
    """
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code, start_year="2022")
        if df is not None and not df.empty:
            latest = df.iloc[0]  # 最新一期
            return {
                "code": code,
                "roe": safe_float(latest.get("净资产收益率(%)", latest.get("加权净资产收益率(%)"))),
                "gross_margin": safe_float(latest.get("销售毛利率(%)", latest.get("主营业务利润率(%)"))),
                "net_margin": safe_float(latest.get("销售净利率(%)", latest.get("净利润率(%)"))),
                "eps": safe_float(latest.get("每股收益(元)", latest.get("基本每股收益(元)"))),
            }
    except Exception as e:
        logger.warning(f"[数据] 获取 {code} 财务指标失败: {e}")
    return {}


# ======================== 板块数据 ========================

@_timer
def fetch_sector_performance(top_n=15):
    """
    获取行业板块涨跌幅排名
    返回: list of dict [{name, change_pct, ...}, ...]
    """
    try:
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            # 尝试常见列名
            name_col = None
            change_col = None
            for c in ["板块名称", "名称", "行业板块"]:
                if c in df.columns:
                    name_col = c
                    break
            for c in ["涨跌幅", "今日涨跌幅"]:
                if c in df.columns:
                    change_col = c
                    break

            if name_col and change_col:
                df[change_col] = pd.to_numeric(df[change_col], errors="coerce")
                df = df.dropna(subset=[change_col])
                df = df.sort_values(change_col, ascending=False)
                top = df.head(top_n)
                bottom = df.tail(5)
                result = []
                for _, row in pd.concat([top, bottom]).iterrows():
                    result.append({
                        "name": str(row[name_col]),
                        "change_pct": safe_float(row[change_col])
                    })
                return result
    except Exception as e:
        logger.error(f"[数据] 获取板块数据失败: {e}")
    return []


# ======================== 北向资金 ========================

@_timer
def fetch_north_flow(days=5):
    """
    获取北向资金净流入数据
    返回: list of dict [{date, net_amount, ...}, ...]
    """
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北向资金")
        if df is not None and not df.empty:
            df = df.tail(days).reset_index(drop=True)
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": str(row.get("日期", row.get("date", ""))),
                    "net_amount": safe_float(
                        row.get("当日净流入", row.get("净流入", 0))
                    ),
                })
            return result
    except Exception as e:
        logger.error(f"[数据] 获取北向资金失败: {e}")
    return []


# ======================== 个股资金流向 ========================

@_timer
def fetch_stock_fund_flow(code):
    """
    获取个股资金流向
    返回: dict {main_net_inflow, huge_net_inflow, ...}
    """
    try:
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        if df is not None and not df.empty:
            code_col = None
            for c in ["代码", "股票代码"]:
                if c in df.columns:
                    code_col = c
                    break
            if code_col:
                row = df[df[code_col].astype(str) == code]
                if not row.empty:
                    row = row.iloc[0]
                    return {
                        "main_net_inflow": safe_float(row.get("主力净流入-净额")),
                        "huge_net_inflow": safe_float(row.get("超大单净流入-净额")),
                        "big_net_inflow": safe_float(row.get("大单净流入-净额")),
                    }
    except Exception as e:
        logger.warning(f"[数据] 获取 {code} 资金流向失败: {e}")
    return {}


# ======================== 大盘指数 ========================

@_timer
def fetch_market_indices():
    """
    获取主要指数行情（上证、深证、创业板、科创50）
    返回: dict {index_name: {price, change_pct, ...}}
    """
    try:
        df = ak.stock_zh_index_spot_em()
        if df is not None and not df.empty:
            targets = {
                "上证指数": "000001",
                "深证成指": "399001",
                "创业板指": "399006",
                "科创50": "000688",
                "沪深300": "000300",
                "中证500": "000905",
                "中证1000": "000852",
            }
            result = {}
            code_col = None
            name_col = None
            for c in ["代码", "指数代码"]:
                if c in df.columns:
                    code_col = c
                    break
            for c in ["名称", "指数名称"]:
                if c in df.columns:
                    name_col = c
                    break
            if code_col and name_col:
                for idx_name, idx_code in targets.items():
                    row = df[df[code_col].astype(str).str.contains(idx_code)]
                    if not row.empty:
                        row = row.iloc[0]
                        result[idx_name] = {
                            "name": idx_name,
                            "price": safe_float(row.get("最新价")),
                            "change_pct": safe_float(row.get("涨跌幅")),
                            "amount": safe_float(row.get("成交额")),
                        }
            return result
    except Exception as e:
        logger.error(f"[数据] 获取大盘指数失败: {e}")
    return {}


# ======================== 龙虎榜 ========================

@_timer
def fetch_dragon_tiger(date_str=None):
    """
    获取龙虎榜数据
    date_str: 格式 'YYYYMMDD'，默认取最近交易日
    返回: list of dict
    """
    if date_str is None:
        date_str = today_str().replace("-", "")
    try:
        df = ak.stock_lhb_detail_em(date=date_str)
        if df is not None and not df.empty:
            result = []
            name_col = None
            for c in ["名称", "股票名称"]:
                if c in df.columns:
                    name_col = c
                    break
            if name_col:
                for _, row in df.head(20).iterrows():
                    result.append({
                        "name": str(row.get(name_col, "")),
                        "reason": str(row.get("上榜原因", "")),
                        "buy_amount": safe_float(row.get("买入额")),
                        "sell_amount": safe_float(row.get("卖出额")),
                        "net_amount": safe_float(row.get("净买额")),
                    })
            return result
    except Exception as e:
        logger.warning(f"[数据] 获取龙虎榜失败: {e}")
    return []
