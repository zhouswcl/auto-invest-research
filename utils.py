"""
===========================================================
  工具函数：时间处理、日志、通用辅助
===========================================================
"""
import os
import sys
import json
import logging
from datetime import datetime, timedelta, timezone


# ======================== 日志配置 ========================

def setup_logger(name="invest_system", level="INFO"):
    """初始化日志器，同时输出到控制台和文件"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    # 控制台
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    # 文件
    os.makedirs("logs", exist_ok=True)
    fh = logging.FileHandler(
        f"logs/{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


logger = setup_logger()


# ======================== 时间工具 ========================

TZ_CN = timezone(timedelta(hours=8))


def beijing_now():
    """获取当前北京时间"""
    return datetime.now(TZ_CN)


def beijing_time_str(fmt="%Y-%m-%d %H:%M:%S"):
    return beijing_now().strftime(fmt)


def today_str():
    return beijing_now().strftime("%Y-%m-%d")


def is_weekday():
    """是否为工作日（周一~周五）"""
    return beijing_now().weekday() < 5


def get_market_phase():
    """
    判断当前处于哪个交易阶段:
      'pre_market'   盘前 (9:00-9:30)
      'morning'      上午盘 (9:30-11:30)
      'noon_break'   午休 (11:30-13:00)
      'afternoon'    下午盘 (13:00-15:00)
      'post_market'  盘后 (15:00 之后)
      'closed'       非交易日
    """
    if not is_weekday():
        return "closed"
    now = beijing_now()
    t = now.hour * 100 + now.minute
    if 900 <= t < 930:
        return "pre_market"
    elif 930 <= t < 1130:
        return "morning"
    elif 1130 <= t < 1300:
        return "noon_break"
    elif 1300 <= t < 1500:
        return "afternoon"
    else:
        return "post_market"


# ======================== 数据工具 ========================

def safe_float(val, default=0.0):
    """安全转 float"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def pct_change_str(pct):
    """格式化涨跌幅，带正负号"""
    if pct > 0:
        return f"+{pct:.2f}%"
    elif pct < 0:
        return f"{pct:.2f}%"
    return "0.00%"


def save_json(data, filepath):
    """保存 JSON 文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath):
    """加载 JSON 文件"""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
