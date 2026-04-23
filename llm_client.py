"""
===========================================================
  DeepSeek 大模型调用模块
  功能：投研报告润色、异动解读、行情分析
  降级机制：调用失败自动返回基础分析结果
===========================================================
"""
import time
import requests
import config
from utils import logger


def call_deepseek(messages, max_tokens=None, temperature=0.7):
    """
    调用 DeepSeek 大模型（带重试和降级）
    messages: list of dict, 格式 [{"role": "user", "content": "..."}]
    返回: str（模型回复内容），失败返回 None
    """
    if not config.DEEPSEEK_API_KEY:
        logger.warning("[LLM] DeepSeek API Key 未配置，跳过调用")
        return None

    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
    }

    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(1, config.LLM_RETRY_COUNT + 1):
        try:
            logger.info(f"[LLM] 第 {attempt}/{config.LLM_RETRY_COUNT} 次调用...")
            resp = requests.post(
                config.DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=config.LLM_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                logger.info(
                    f"[LLM] 调用成功，tokens: {usage.get('total_tokens', 'N/A')}"
                )
                return content
            else:
                logger.warning(f"[LLM] 返回格式异常: {data}")

        except requests.exceptions.Timeout:
            logger.warning(f"[LLM] 第 {attempt} 次超时")
        except requests.exceptions.ConnectionError:
            logger.warning(f"[LLM] 第 {attempt} 次连接失败")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "N/A"
            logger.warning(f"[LLM] 第 {attempt} 次 HTTP 错误: {status}")
        except Exception as e:
            logger.warning(f"[LLM] 第 {attempt} 次异常: {e}")

        if attempt < config.LLM_RETRY_COUNT:
            time.sleep(config.LLM_RETRY_DELAY * attempt)

    logger.error("[LLM] 全部重试失败，启用降级模式")
    return None


# ======================== 业务封装 ========================

SYSTEM_PROMPT = """你是一位资深的中国A股投研分析师，精通技术分析、基本面分析和市场情绪分析。
你的回复应当：
1. 专业、简洁、有条理
2. 使用中文
3. 包含明确的观点和逻辑
4. 适当使用数据和指标支撑
5. 不做绝对的买卖建议，但要给出方向性判断"""


def polish_daily_report(raw_report):
    """用 DeepSeek 润色每日投研日报"""
    logger.info("[LLM] 润色每日投研日报...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请润色以下投研日报，优化语言表达、梳理逻辑、使报告更加专业化和机构化。保持核心数据和分析结论不变。\n\n---原始报告---\n{raw_report}\n---结束---"},
    ]
    result = call_deepseek(messages, max_tokens=4000, temperature=0.5)
    return result if result else raw_report


def interpret_anomaly(stock_name, anomaly_desc, realtime_info=None):
    """用 DeepSeek 解读个股异动原因"""
    logger.info(f"[LLM] 解读 {stock_name} 异动...")
    info_str = ""
    if realtime_info:
        info_str = (
            f"当前价格: {realtime_info.get('price', 'N/A')}，"
            f"涨跌幅: {realtime_info.get('change_pct', 'N/A')}%，"
            f"成交量: {realtime_info.get('volume', 'N/A')}，"
            f"换手率: {realtime_info.get('turnover', 'N/A')}%"
        )
    messages = [
        {"role": "system", "content": "你是一位资深A股投研分析师。请简要解读以下个股异动的可能原因（2-3句话即可），不要做买卖建议。"},
        {"role": "user", "content": f"个股: {stock_name}\n异动描述: {anomaly_desc}\n{info_str}\n\n请简要解读可能的异动原因："},
    ]
    result = call_deepseek(messages, max_tokens=300, temperature=0.6)
    return result if result else "（大模型暂不可用，请关注该股后续走势及公告信息）"


def generate_market_outlook(market_summary):
    """用 DeepSeek 生成市场展望"""
    logger.info("[LLM] 生成市场展望...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"基于以下今日市场数据，请给出明日市场展望（3-5句话），包含大盘走势判断和重点关注方向：\n\n{market_summary}"},
    ]
    result = call_deepseek(messages, max_tokens=500, temperature=0.6)
    return result if result else "（大模型暂不可用，请关注技术面和资金面变化）"


def summarize_stock(stock_name, analysis_data):
    """用 DeepSeek 生成个股投研摘要"""
    logger.info(f"[LLM] 生成 {stock_name} 投研摘要...")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请基于以下分析数据，为{stock_name}生成一段简短的投研摘要（3-5句话），突出核心观点：\n\n{analysis_data}"},
    ]
    result = call_deepseek(messages, max_tokens=300, temperature=0.5)
    return result if result else ""
