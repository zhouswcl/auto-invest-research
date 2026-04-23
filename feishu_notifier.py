"""
===========================================================
  飞书推送模块
  支持：文本消息、富文本（post）消息、交互卡片
===========================================================
"""
import json
import requests
import config
from utils import logger


def _send(payload):
    """通用发送方法"""
    if not config.FEISHU_WEBHOOK:
        logger.error("[飞书] Webhook 地址未配置")
        return False
    try:
        resp = requests.post(
            config.FEISHU_WEBHOOK,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("[飞书] 推送成功")
            return True
        else:
            logger.warning(f"[飞书] 推送返回异常: {result}")
            return False
    except Exception as e:
        logger.error(f"[飞书] 推送失败: {e}")
        return False


def send_text(text):
    """发送纯文本消息"""
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    return _send(payload)


def send_post(title, content_lines):
    """
    发送富文本消息（飞书 post 格式）
    title: str 标题
    content_lines: list of str 每行内容
    """
    # 将内容行转为飞书富文本格式
    post_content = []
    for line in content_lines:
        if not line.strip():
            post_content.append([{"tag": "text", "text": "\n"}])
        elif line.startswith("# ") or line.startswith("【"):
            post_content.append([
                {"tag": "text", "text": line + "\n"}
            ])
        else:
            post_content.append([
                {"tag": "text", "text": line + "\n"}
            ])

    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": post_content,
                }
            }
        },
    }
    return _send(payload)


def send_daily_report(report_text):
    """推送每日投研日报"""
    lines = report_text.split("\n")
    # 第一行作为标题
    title = "📊 每日投研日报"
    return send_text(report_text)


def send_alert(alert_text):
    """推送异动提醒"""
    return send_text(alert_text)


def send_system_status(status_text):
    """推送系统状态"""
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🤖 系统状态通知"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": status_text},
                }
            ],
        },
    }
    return _send(payload)


def send_error_alert(error_msg):
    """推送错误告警"""
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ 系统异常告警"},
                "template": "red",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**错误信息:**\n{error_msg}"},
                }
            ],
        },
    }
    return _send(payload)
