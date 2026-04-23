"""
===========================================================
  个股异动监控模块
  支持价格异动、成交量异动、技术信号异动
  异动触发后调用 DeepSeek 解读
===========================================================
"""
import config
from utils import logger, pct_change_str
from data_fetcher import fetch_stock_pool_quotes, fetch_stock_history, fetch_stock_fund_flow
from research_analyzer import analyze_technical
import llm_client


def check_price_alert(realtime_info):
    """检查价格异动（涨跌幅超限）"""
    alerts = []
    cfg = config.ALERT_CONFIG
    name = realtime_info.get("name", "")
    code = realtime_info.get("code", "")
    pct = realtime_info.get("change_pct", 0)

    if pct >= cfg["price_up_pct"]:
        alerts.append({
            "alert_type": "📈 大涨提醒",
            "description": f"涨幅达 {pct:.2f}%，超过{cfg['price_up_pct']}%阈值",
            "severity": "high" if pct >= 7 else "medium",
        })
    if pct <= -cfg["price_down_pct"]:
        alerts.append({
            "alert_type": "📉 大跌提醒",
            "description": f"跌幅达 {abs(pct):.2f}%，超过{cfg['price_down_pct']}%阈值",
            "severity": "high" if pct <= -7 else "medium",
        })

    # 涨停/跌停检测
    if cfg.get("limit_up_alert") and pct >= 9.8:
        alerts.append({
            "alert_type": "🔴 涨停",
            "description": f"触及涨停（涨幅 {pct:.2f}%）",
            "severity": "high",
        })
    if cfg.get("limit_down_alert") and pct <= -9.8:
        alerts.append({
            "alert_type": "🟢 跌停",
            "description": f"触及跌停（跌幅 {abs(pct):.2f}%）",
            "severity": "high",
        })

    return alerts


def check_volume_alert(realtime_info):
    """检查成交量/换手率异动"""
    alerts = []
    cfg = config.ALERT_CONFIG
    name = realtime_info.get("name", "")

    vol_ratio = realtime_info.get("volume_ratio", 0)
    if vol_ratio >= cfg["volume_ratio"]:
        alerts.append({
            "alert_type": "📊 放量提醒",
            "description": f"量比 {vol_ratio:.1f}，超过{cfg['volume_ratio']}阈值",
            "severity": "medium",
        })

    turnover = realtime_info.get("turnover", 0)
    if turnover >= cfg["turnover_rate"]:
        alerts.append({
            "alert_type": "🔄 高换手",
            "description": f"换手率 {turnover:.1f}%，超过{cfg['turnover_rate']}%阈值",
            "severity": "medium",
        })

    return alerts


def check_technical_signal_alert(code, name, history_df, realtime_info):
    """检查技术信号异动"""
    alerts = []
    tech = analyze_technical(history_df, realtime_info)

    for sig in tech.get("signals", []):
        severity = "high" if "金叉" in sig or "死叉" in sig else "low"
        alerts.append({
            "alert_type": f"📐 技术信号",
            "description": sig,
            "severity": severity,
        })

    return alerts


def run_full_monitoring():
    """
    执行完整的股票池监控
    返回: list of dict（异动详情）
    """
    logger.info("[监控] 开始执行股票池监控...")
    all_alerts = []

    # 1. 获取股票池实时行情
    quotes = fetch_stock_pool_quotes(config.STOCK_POOL)
    if not quotes:
        logger.warning("[监控] 股票池行情为空")
        return all_alerts

    for code, name in config.STOCK_POOL:
        info = quotes.get(code)
        if not info:
            continue

        stock_alerts = []

        # 2. 价格异动检查
        stock_alerts.extend(check_price_alert(info))

        # 3. 成交量异动检查
        stock_alerts.extend(check_volume_alert(info))

        # 4. 技术信号检查（有信号时才做）
        try:
            history = fetch_stock_history(code, days=30)
            if history is not None and not history.empty:
                tech_alerts = check_technical_signal_alert(code, name, history, info)
                stock_alerts.extend(tech_alerts)
        except Exception as e:
            logger.warning(f"[监控] {name} 技术分析异常: {e}")

        # 5. 对重要异动调用 DeepSeek 解读
        for alert in stock_alerts:
            if alert.get("severity") == "high":
                try:
                    interpretation = llm_client.interpret_anomaly(name, alert["description"], info)
                    alert["llm_interpretation"] = interpretation
                except Exception as e:
                    logger.warning(f"[监控] {name} LLM解读失败: {e}")

        # 组装完整异动记录
        for alert in stock_alerts:
            alert.update({
                "code": code,
                "name": name,
                "price": info.get("price"),
                "change_pct": info.get("change_pct"),
                "time": config.TZ_OFFSET,
            })
            all_alerts.append(alert)

        logger.info(f"[监控] {name}: 发现 {len(stock_alerts)} 项异动")

    # 按严重程度排序
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_alerts.sort(key=lambda x: severity_order.get(x.get("severity", 2), 2))

    logger.info(f"[监控] 监控完成，共发现 {len(all_alerts)} 项异动")
    return all_alerts
