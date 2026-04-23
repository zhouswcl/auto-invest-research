"""
===========================================================
  报告生成模块
  生成每日投研日报（纯文本/Markdown 格式）
  支持 DeepSeek 大模型润色
===========================================================
"""
from utils import logger, pct_change_str, beijing_time_str
import llm_client


def generate_daily_report(market_indices, sector_data, stock_analyses,
                          north_flow, dragon_tiger, use_llm=True):
    """
    生成完整的每日投研日报
    返回: str（Markdown 格式文本）
    """
    lines = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 每日投研日报 | {beijing_time_str('%Y年%m月%d日 %A')}")
    lines.append(f"⏰ 生成时间: {beijing_time_str('%H:%M')}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # ---- 一、大盘概览 ----
    lines.append("【一、大盘概览】")
    if market_indices:
        for idx_name, idx_data in market_indices.items():
            chg = idx_data.get("change_pct", 0)
            lines.append(
                f"  {idx_name}: {idx_data.get('price', 'N/A')} "
                f"({pct_change_str(chg)})"
            )
    else:
        lines.append("  暂无大盘数据")
    lines.append("")

    # ---- 二、板块动态 ----
    lines.append("【二、板块涨跌 TOP/BOTTOM】")
    if sector_data:
        top_sectors = [s for s in sector_data if s["change_pct"] > 0][:5]
        bottom_sectors = sorted(sector_data, key=lambda x: x["change_pct"])[:5]
        if top_sectors:
            lines.append("  🔥 领涨板块:")
            for s in top_sectors:
                lines.append(f"    {s['name']}  {pct_change_str(s['change_pct'])}")
        if bottom_sectors:
            lines.append("  ❄️ 领跌板块:")
            for s in bottom_sectors:
                lines.append(f"    {s['name']}  {pct_change_str(s['change_pct'])}")
    else:
        lines.append("  暂无板块数据")
    lines.append("")

    # ---- 三、北向资金 ----
    lines.append("【三、北向资金】")
    if north_flow:
        for item in north_flow[-3:]:
            net = item.get("net_amount", 0)
            direction = "净流入" if net > 0 else "净流出"
            lines.append(f"  {item.get('date', '')}: {direction} {abs(net):.2f} 亿元")
    else:
        lines.append("  暂无北向资金数据")
    lines.append("")

    # ---- 四、龙虎榜 ----
    lines.append("【四、龙虎榜精选】")
    if dragon_tiger:
        for dt in dragon_tiger[:8]:
            net = dt.get("net_amount", 0)
            direction = "净买入" if net > 0 else "净卖出"
            lines.append(
                f"  {dt.get('name', '')}  {direction} {abs(net)/1e8:.2f}亿  "
                f"({dt.get('reason', '')})"
            )
    else:
        lines.append("  今日无龙虎榜数据")
    lines.append("")

    # ---- 五、股票池分析 ----
    lines.append("【五、股票池综合分析】")
    if stock_analyses:
        # 按评分排序
        sorted_stocks = sorted(stock_analyses, key=lambda x: x.get("score", 0), reverse=True)
        for sa in sorted_stocks:
            lines.append(f"\n  ▶ {sa['name']}（{sa['code']}） {sa['rating']}")
            lines.append(f"    现价: {sa['price']}  涨跌幅: {pct_change_str(sa['change_pct'])}")
            if sa.get("fundamental"):
                lines.append(f"    基本面: {sa['fundamental']}")
            if sa.get("fund_flow"):
                lines.append(f"    资金面: {sa['fund_flow']}")
            lines.append(f"    趋势: {sa.get('trend', '')}")
            if sa.get("signals"):
                lines.append(f"    信号: {'; '.join(sa['signals'][:5])}")
            lines.append(f"    支撑: {sa.get('support', 'N/A')}  压力: {sa.get('resistance', 'N/A')}")
    else:
        lines.append("  暂无股票池分析数据")
    lines.append("")

    # ---- 六、异动汇总 ----
    lines.append("【六、今日异动汇总】")
    lines.append("  （详见盘中实时推送）")
    lines.append("")

    # ---- 七、明日关注 ----
    lines.append("【七、明日关注】")
    lines.append("  （将由 AI 模型生成，详见下方）")
    lines.append("")

    raw_report = "\n".join(lines)

    # 调用 DeepSeek 润色
    if use_llm:
        try:
            polished = llm_client.polish_daily_report(raw_report)
            if polished and len(polished) > len(raw_report) * 0.5:
                return polished
        except Exception as e:
            logger.warning(f"[报告] LLM 润色失败: {e}")

    return raw_report


def generate_monitoring_alerts(alerts):
    """生成异动提醒消息文本"""
    if not alerts:
        return "当前无异动。"

    lines = ["🔔 个股异动实时提醒\n"]
    for alert in alerts:
        lines.append(f"\n⚠️ {alert['name']}（{alert['code']}）")
        lines.append(f"  异动类型: {alert['alert_type']}")
        lines.append(f"  详细描述: {alert['description']}")
        lines.append(f"  当前价格: {alert.get('price', 'N/A')}")
        lines.append(f"  涨跌幅: {pct_change_str(alert.get('change_pct', 0))}")
        if alert.get("llm_interpretation"):
            lines.append(f"  🤖 AI解读: {alert['llm_interpretation']}")

    return "\n".join(lines)
