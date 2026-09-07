"""
Universal Webpage & Element Monitor (CLI Edition)
"""

import os
import sys
import time
import datetime
import argparse
import subprocess
import base64
import html as html_lib
import urllib3
import requests
from lxml import html

# Try importing winsound for Windows audio alerts; fallback to terminal bell
try:
    import winsound
    def play_sound(freq_pattern=None):
        if freq_pattern is None:
            freq_pattern = [(1000, 200), (1200, 200), (1500, 400)]
        for freq, duration in freq_pattern:
            winsound.Beep(freq, duration)
            time.sleep(0.05)
except ImportError:
    def play_sound(freq_pattern=None):
        print("\a", end="", flush=True)

# Disable SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def send_desktop_notification(title: str, message: str):
    """Sends a native Windows Toast notification banner."""
    try:
        escaped_title = html_lib.escape(title)
        escaped_message = html_lib.escape(message)
        ps_script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = '<toast><visual><binding template="ToastGeneric"><text>{escaped_title}</text><text>{escaped_message}</text></binding></visual></toast>'
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Universal Web Monitor').Show($toast)
"""
        encoded = base64.b64encode(ps_script.encode('utf-16le')).decode('utf-8')
        subprocess.Popen(
            ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"⚠️  Desktop notification error: {e}")

def resolve_telegram_chat_id(bot_token: str, chat_id: str = None) -> str | None:
    """Auto-detects chat ID from messages sent to the bot."""
    if chat_id and chat_id.strip():
        return chat_id.strip()

    if not bot_token:
        return None

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("ok") and data.get("result"):
            last_update = data["result"][-1]
            found_id = str(last_update.get("message", {}).get("chat", {}).get("id") or 
                           last_update.get("channel_post", {}).get("chat", {}).get("id"))
            if found_id:
                return found_id
    except Exception as e:
        print(f"⚠️  Could not fetch Telegram updates: {e}")
    return None

def send_telegram_notification(bot_token: str, chat_id: str, message: str) -> bool:
    """Sends a message to your Telegram account."""
    if not bot_token or not chat_id:
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("📱 Telegram notification sent successfully!")
            return True
        else:
            print(f"⚠️  Telegram API error ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"⚠️  Failed to send Telegram notification: {e}")
    return False

def get_element_content(session: requests.Session, url: str, xpath_query: str) -> str | None:
    """Fetches the webpage and extracts the text content of the target XPath."""
    response = session.get(url, headers=HEADERS, timeout=15, verify=False)
    response.raise_for_status()
    tree = html.fromstring(response.content)
    elements = tree.xpath(xpath_query)
    if elements:
        if isinstance(elements[0], str):
            return elements[0].strip()
        return elements[0].text_content().strip()
    return None

def main():
    parser = argparse.ArgumentParser(description="Universal Webpage & Element Monitor")
    parser.add_argument("--url", "-u", default=os.getenv("TARGET_URL"), help="Target website URL")
    parser.add_argument("--xpath", "-x", default=os.getenv("TARGET_XPATH"), help="Target XPath expression")
    parser.add_argument("--interval", "-i", type=int, default=int(os.getenv("CHECK_INTERVAL", 30)), help="Polling interval in seconds")
    parser.add_argument("--bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram Bot Token (Optional)")
    parser.add_argument("--chat-id", default=os.getenv("TELEGRAM_CHAT_ID"), help="Telegram Chat ID (Optional)")

    args = parser.parse_args()

    url = args.url
    xpath_query = args.xpath
    interval = max(args.interval, 3)
    bot_token = args.bot_token
    chat_id = args.chat_id

    if not url:
        url = input("Enter Target Website URL: ").strip()
    if not xpath_query:
        xpath_query = input("Enter Target XPath: ").strip()

    if not url or not xpath_query:
        print("❌ Error: Both URL and XPath are required.")
        sys.exit(1)

    print("=" * 65)
    print(" 🔍 Universal Web Monitor (CLI)")
    print(f" URL:      {url}")
    print(f" XPath:    {xpath_query}")
    print(f" Interval: {interval} seconds")
    print("=" * 65)

    if bot_token:
        chat_id = resolve_telegram_chat_id(bot_token, chat_id)
        if chat_id:
            print(f" Connected to Telegram (Chat ID: {chat_id})")
        else:
            print("💡 Tip: Send any message to your bot on Telegram to connect alerts.")

    session = requests.Session()
    last_value = None

    print("\n⏳ Fetching initial element value...")
    try:
        initial_val = get_element_content(session, url, xpath_query)
    except Exception as e:
        print(f"⚠️  Initial fetch failed: {e}")
        initial_val = None

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if initial_val:
        last_value = initial_val
        print(f"[{now}] 📌 Initial Value Detected: '{initial_val}'\n")

        send_desktop_notification(
            "Web Monitor Started",
            f"Monitoring active! Initial value: {initial_val}"
        )
        play_sound([(800, 150), (1200, 200)])

        if bot_token and chat_id:
            send_telegram_notification(
                bot_token, chat_id,
                f"🚀 *Web Monitor Started*\n\n"
                f"• *URL:* {url}\n"
                f"• *Initial Value:* `{initial_val}`\n"
                f"• *Interval:* {interval}s"
            )
    else:
        print(f"[{now}] ⚠️  Element not detected yet, will retry during loop.\n")

    print("-" * 65)
    print(" 🟢 Actively monitoring... (Press Ctrl+C to stop)")
    print("-" * 65)

    try:
        while True:
            time.sleep(interval)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if bot_token and not chat_id:
                resolved = resolve_telegram_chat_id(bot_token)
                if resolved:
                    chat_id = resolved
                    print(f"[{now}] 📱 Telegram Chat Connected (ID: {chat_id})")

            try:
                current_value = get_element_content(session, url, xpath_query)

                if current_value is None:
                    print(f"[{now}] ⚠️  Element not found on page.")
                else:
                    if last_value is None:
                        print(f"[{now}] 📌 Initial Value: '{current_value}'")
                        last_value = current_value
                    elif current_value != last_value:
                        # Change Detected!
                        print(f"\n{'!' * 65}")
                        print(f"[{now}] 🚨 CHANGE DETECTED!")
                        print(f" Previous: '{last_value}'")
                        print(f" New:      '{current_value}'")
                        print(f"{'!' * 65}\n")

                        send_desktop_notification(
                            "🚨 Website Change Detected!",
                            f"New: {current_value} (was {last_value})"
                        )
                        play_sound()

                        if bot_token and chat_id:
                            msg = (
                                f"🚨 *Website Change Detected!*\n\n"
                                f"• *Previous:* {last_value}\n"
                                f"• *New:* {current_value}\n\n"
                                f"🔗 [Open Target Page]({url})"
                            )
                            send_telegram_notification(bot_token, chat_id, msg)

                        last_value = current_value
                    else:
                        print(f"[{now}] ⏱️  No change (Value: '{current_value}')")

            except requests.RequestException as req_err:
                print(f"[{now}] ❌ Network error: {req_err}")
            except Exception as e:
                print(f"[{now}] ❌ Error: {e}")

    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped by user.")

if __name__ == "__main__":
    main()
