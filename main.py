"""
===========================================================
  程序主入口
  根据 RUN_MODE 和当前市场时段自动选择运行模式:
    - pre_market: 盘前分析
    - intraday: 盘中监控
    - post_market: 盘后日报
===========================================================
"""
import time
import sys
import traceback

import config
from utils import logger, beijing_time_str, get_market_phase, is_weekday, save_json
from data_fetcher import (
    fetch_market_indices, fetch_sector_performance,
    fetch_north_flow, fetch_dragon_tiger,
    fetch_stock_pool_quotes, fetch_stock_history,
    fetch_financial_indicator, fetch_stock_fund_flow,
)
from research_analyzer import comprehensive_stock_analysis
from monitor import run_full_monitoring
from report_generator import generate_daily_report, generate_monitoring_alerts
from llm_client import generate_market_outlook
from feishu_notifier import (
    send_text, send_daily_report, send_alert, send_system_status, send_error_alert
)


def run_pre_market():
    """盘前分析：获取隔夜数据，生成早盘关注"""
    logger.info("=" * 50)
    logger.info("[盘前] 开始盘前分析...")
    logger.info("=" * 50)

    try:
        # 获取大盘指数
        indices = fetch_market_indices()
        # 获取板块数据
        sectors = fetch_sector_performance()
        # 获取北向资金
        north = fetch_north_flow(5)

        # 股票池快照
        quotes = fetch_stock_pool_quotes(config.STOCK_POOL)
        stock_summaries = []
        if quotes:
            for code, name in config.STOCK_POOL:
                info = quotes.get(code)
                if info:
                    chg = info.get("change_pct", 0)
                    stock_summaries.append(f"  {name}: {info.get('price', 'N/A')} ({chg:+.2f}%)")

        msg_lines = [
            "🌅 【盘前速览】",
            f"⏰ {beijing_time_str('%Y-%m-%d %H:%M')}\n",
        ]

        # 大盘
        msg_lines.append("📊 大盘隔夜情况:")
        if indices:
            for idx_name, idx_data in indices.items():
                chg = idx_data.get("change_pct", 0)
                arrow = "🔴" if chg < 0 else "🟢"
                msg_lines.append(f"  {arrow} {idx_name}: {idx_data.get('price', 'N/A')} ({chg:+.2f}%)")
        else:
            msg_lines.append("  暂无数据")
        msg_lines.append("")

        # 北向资金
        msg_lines.append("💰 北向资金近期动向:")
        if north:
            for item in north[-3:]:
                net = item.get("net_amount", 0)
                direction = "流入" if net > 0 else "流出"
                msg_lines.append(f"  {item.get('date', '')}: 净{direction} {abs(net):.2f} 亿")
        msg_lines.append("")

        # 板块
        if sectors:
            top5 = sectors[:5]
            msg_lines.append("🔥 近期领涨板块:")
            for s in top5:
                msg_lines.append(f"  {s['name']} ({s['change_pct']:+.2f}%)")
        msg_lines.append("")

        # 股票池
        if stock_summaries:
            msg_lines.append("📋 股票池最新行情:")
            msg_lines.extend(stock_summaries)
        msg_lines.append("")

        msg_lines.append("💡 盘前提示：请关注开盘后异动情况，系统将在盘中持续监控。")

        message = "\n".join(msg_lines)
        send_text(message)
        logger.info("[盘前] 盘前分析推送完成")
        return True

    except Exception as e:
        logger.error(f"[盘前] 盘前分析异常: {e}")
        logger.error(traceback.format_exc())
        send_error_alert(f"盘前分析失败: {str(e)}")
        return False


def run_intraday_monitoring():
    """盘中监控：检测异动并实时推送"""
    logger.info("=" * 50)
    logger.info("[盘中] 开始盘中监控...")
    logger.info("=" * 50)

    try:
        alerts = run_full_monitoring()

        if alerts:
            alert_text = generate_monitoring_alerts(alerts)
            send_alert(alert_text)
            logger.info(f"[盘中] 推送 {len(alerts)} 条异动提醒")
        else:
            logger.info("[盘中] 当前无异动")

        # 保存异动记录
        save_json(alerts, f"data/alerts_{beijing_time_str('%Y%m%d_%H%M')}.json")
        return True

    except Exception as e:
        logger.error(f"[盘中] 盘中监控异常: {e}")
        logger.error(traceback.format_exc())
        send_error_alert(f"盘中监控失败: {str(e)}")
        return False


def run_post_market_report():
    """盘后日报：生成完整投研报告"""
    logger.info("=" * 50)
    logger.info("[盘后] 开始生成投研日报...")
    logger.info("=" * 50)

    total_start = time.time()

    try:
        # 1. 获取大盘数据
        logger.info("[盘后] 获取大盘数据...")
        indices = fetch_market_indices()

        # 2. 获取板块数据
        logger.info("[盘后] 获取板块数据...")
        sectors = fetch_sector_performance()

        # 3. 获取北向资金
        logger.info("[盘后] 获取北向资金...")
        north = fetch_north_flow(5)

        # 4. 获取龙虎榜
        logger.info("[盘后] 获取龙虎榜...")
        from utils import today_str
        dt_str = today_str().replace("-", "")
        dragon = fetch_dragon_tiger(dt_str)

        # 5. 股票池综合分析
        logger.info("[盘后] 开始股票池综合分析...")
        quotes = fetch_stock_pool_quotes(config.STOCK_POOL)
        stock_analyses = []

        for code, name in config.STOCK_POOL:
            logger.info(f"[盘后] 分析 {name}（{code}）...")
            info = quotes.get(code, {})

            # 历史K线
            history = fetch_stock_history(code, days=60)
            # 财务数据
            financial = fetch_financial_indicator(code)
            # 资金流向
            fund_flow = fetch_stock_fund_flow(code)

            # 综合分析
            analysis = comprehensive_stock_analysis(
                code, name, history, info, financial, fund_flow
            )
            stock_analyses.append(analysis)

            # 每分析几只推送一次系统状态，避免超时
            idx = config.STOCK_POOL.index((code, name))
            if (idx + 1) % 4 == 0:
                send_system_status(
                    f"日报生成中... 已完成 {idx + 1}/{len(config.STOCK_POOL)} 只股票分析"
                )

        # 6. 生成报告
        logger.info("[盘后] 生成报告...")
        report = generate_daily_report(
            indices, sectors, stock_analyses, north, dragon, use_llm=True
        )

        # 7. 调用 DeepSeek 生成明日展望（如果 API Key 可用）
        try:
            market_summary = f"大盘: {indices}\n板块: {sectors[:5]}\n北向: {north[-1] if north else '无'}"
            outlook = generate_market_outlook(market_summary)
            if outlook:
                report += f"\n\n【🤖 AI 明日展望】\n{outlook}"
        except Exception as e:
            logger.warning(f"[盘后] 生成明日展望失败: {e}")

        # 8. 推送报告
        send_daily_report(report)

        # 9. 保存报告到文件
        save_json({
            "date": beijing_time_str("%Y-%m-%d"),
            "report": report,
            "stock_analyses": stock_analyses,
        }, f"data/report_{beijing_time_str('%Y%m%d')}.json")

        elapsed = time.time() - total_start
        logger.info(f"[盘后] 日报生成并推送完成，耗时 {elapsed:.1f} 秒")
        send_system_status(f"✅ 每日投研日报已生成并推送（耗时 {elapsed:.0f} 秒）")
        return True

    except Exception as e:
        logger.error(f"[盘后] 盘后日报异常: {e}")
        logger.error(traceback.format_exc())
        send_error_alert(f"盘后日报生成失败: {str(e)}")
        return False


def main():
    """主入口"""
    logger.info("=" * 60)
    logger.info(f"🚀 全自动投研系统启动 | {beijing_time_str()}")
    logger.info(f"📋 运行模式: {config.RUN_MODE}")
    logger.info(f"⏰ 市场阶段: {get_market_phase()}")
    logger.info("=" * 60)

    # 检查必配参数
    if not config.FEISHU_WEBHOOK:
        logger.error("❌ FEISHU_WEBHOOK 未配置！请在 GitHub Secrets 中添加。")
        sys.exit(1)

    if not config.DEEPSEEK_API_KEY:
        logger.warning("⚠️ DEEPSEEK_API_KEY 未配置，将使用基础分析模式（无 AI 润色）")

    phase = get_market_phase()
    mode = config.RUN_MODE

    # 判断是否为交易日
    if phase == "closed" and mode != "full":
        logger.info("今天是非交易日（周末），系统自动跳过")
        send_system_status("今天是非交易日，系统已自动跳过。周一见！👋")
        return

    # 根据模式和市场阶段决定执行内容
    success = False

    if mode == "daily":
        # 仅日报模式：任何时段都生成日报
        success = run_post_market_report()

    elif mode == "monitor":
        # 仅监控模式
        success = run_intraday_monitoring()

    elif mode == "full":
        # 全量模式：根据时段自动选择
        if phase in ("pre_market", "morning"):
            run_pre_market()
            run_intraday_monitoring()
            success = True
        elif phase == "afternoon":
            run_intraday_monitoring()
            success = True
        elif phase == "post_market":
            run_intraday_monitoring()
            run_post_market_report()
            success = True
        else:
            logger.info("当前时段无需执行，等待下一调度周期")
            success = True
    else:
        logger.error(f"未知运行模式: {mode}")
        sys.exit(1)

    if success:
        logger.info("✅ 系统运行完成")
    else:
        logger.warning("⚠️ 系统运行过程中存在异常，请查看日志")
        send_error_alert("系统运行异常，请检查 GitHub Actions 日志。")

    logger.info(f"⏱ 系统结束 | {beijing_time_str()}")


if __name__ == "__main__":
    main()
