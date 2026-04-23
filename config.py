"""
===========================================================
  全局配置文件
  敏感参数请配置在 GitHub Secrets 中，代码会自动读取
===========================================================
"""
import os

# ======================== GitHub Secrets 自动读取 ========================
# 以下参数在 GitHub 仓库 → Settings → Secrets → Actions 中配置

# 【必填】飞书自定义机器人 Webhook 地址
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

# 【必填】DeepSeek 大模型 API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# 【可选】Tushare 接口 Token（未配置时自动使用 AkShare 免费接口）
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

# 【可选】运行模式: daily=仅日报, monitor=仅监控, full=全量运行
RUN_MODE = os.environ.get("RUN_MODE", "full")


# ======================== DeepSeek 大模型配置 ========================

DEEPSEEK_API_URL = os.environ.get(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions"
)
LLM_MODEL = "deepseek-chat"          # 模型名称
LLM_TIMEOUT = 15                     # 单次调用超时（秒）
LLM_MAX_TOKENS = 4000                # 最大生成 token 数
LLM_RETRY_COUNT = 3                  # 失败重试次数
LLM_RETRY_DELAY = 2                  # 重试间隔（秒）


# ======================== 股票池配置 ========================
# 用户可自由增删股票，格式: (代码, 名称)
# 代码格式: 6位数字，上海以6开头，深圳以0或3开头

STOCK_POOL = [
    ("600519", "贵州茅台"),
    ("000858", "五粮液"),
    ("601318", "中国平安"),
    ("000001", "平安银行"),
    ("600036", "招商银行"),
    ("300750", "宁德时代"),
    ("002594", "比亚迪"),
    ("600900", "长江电力"),
    ("601899", "紫金矿业"),
    ("000333", "美的集团"),
    ("601012", "隆基绿能"),
    ("300059", "东方财富"),
]


# ======================== 异动监控阈值 ========================

ALERT_CONFIG = {
    "price_up_pct": 3.0,             # 涨幅超过此值 → 触发提醒（%）
    "price_down_pct": 3.0,           # 跌幅超过此值 → 触发提醒（%）
    "volume_ratio": 2.5,             # 量比超过此值 → 触发提醒
    "turnover_rate": 5.0,            # 换手率超过此值 → 触发提醒（%）
    "north_net_flow": 5.0,           # 北向资金单日净流入/出超过此值（亿元）
    "limit_up_alert": True,          # 是否监控涨停
    "limit_down_alert": True,        # 是否监控跌停
}


# ======================== 系统参数 ========================

LOG_LEVEL = "INFO"
TIMEZONE_OFFSET = 8                  # 北京时间 UTC+8
MARKET_OPEN_HOUR = 9                 # 开盘时间
MARKET_OPEN_MIN = 30
MARKET_CLOSE_HOUR = 15               # 收盘时间
MARKET_CLOSE_MIN = 0
