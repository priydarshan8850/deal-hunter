"""Send deal alerts: email (SMTP), Windows toast popup, optional Telegram.

All senders are best-effort - a broken channel never breaks the check run.
"""
from __future__ import annotations

import base64
import smtplib
import subprocess
import sys
from email.message import EmailMessage

_TOAST_PS = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $template.GetElementsByTagName('text')
$texts.Item(0).AppendChild($template.CreateTextNode({title})) | Out-Null
$texts.Item(1).AppendChild($template.CreateTextNode({body})) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Deal Hunter').Show($toast)
"""


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def windows_toast(title: str, body: str) -> bool:
    """Show a Windows 10/11 notification. No extra packages needed."""
    if sys.platform != "win32":
        return False
    body = " ".join(str(body).split())[:220]
    script = _TOAST_PS.replace("{title}", _ps_quote(title)).replace("{body}", _ps_quote(body))
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def send_email(alert: dict, settings) -> bool:
    """Email one alert. Returns True when delivered."""
    if not settings.email_enabled:
        return False
    message = EmailMessage()
    message["Subject"] = alert["title"]
    message["From"] = settings.smtp_user
    message["To"] = settings.email_to
    message.set_content(alert["body"] + "\n\n-- Deal Hunter")
    try:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.login(settings.smtp_user, settings.smtp_pass)
            smtp.send_message(message)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"email failed: {exc}")
        return False


def send_telegram(alert: dict, settings) -> bool:
    """Optional: reuse a Telegram bot to push the alert."""
    if not (settings.telegram_token and settings.telegram_chat_id):
        return False
    try:
        import httpx

        resp = httpx.post(
            f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage",
            json={
                "chat_id": settings.telegram_chat_id,
                "text": f"{alert['title']}\n\n{alert['body']}",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        return resp.status_code == 200
    except Exception as exc:  # noqa: BLE001
        print(f"telegram failed: {exc}")
        return False


def send_all(alerts: list[dict], settings) -> int:
    """Send every alert on every configured channel. Returns alerts delivered somewhere."""
    delivered = 0
    for alert in alerts:
        ok = False
        ok = send_email(alert, settings) or ok
        ok = windows_toast(alert["title"], alert["body"]) or ok
        ok = send_telegram(alert, settings) or ok
        if ok:
            delivered += 1
    return delivered
