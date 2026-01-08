import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Target URL for announcements
TARGET_URL = "https://ggfw.hrss.gd.gov.cn/gwyks/anouns.do"
HISTORY_FILE = "history.json"

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

import subprocess

def fetch_announcements():
    try:
        # Use curl via subprocess for better TLS compatibility with government sites
        result = subprocess.run([
            "curl", "-s", "-L",
            "-H", f"User-Agent: {HEADERS['User-Agent']}",
            TARGET_URL
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Curl error: {result.stderr}")
            return None
            
        return result.stdout
    except Exception as e:
        print(f"Error fetching page via curl: {e}")
        return None

def parse_announcements(html):
    soup = BeautifulSoup(html, "html.parser")
    announcements = []
    
    # Based on our research, items are in .notice-list ul li
    list_items = soup.select(".notice-list ul li")
    for item in list_items:
        a_tag = item.find("a")
        span_tag = item.find("span")
        
        if a_tag:
            title = a_tag.get_text(strip=True)
            # The link is often in onclick="openLinkWindow('URL')"
            onclick = a_tag.get("onclick", "")
            if "openLinkWindow('" in onclick:
                link = onclick.split("'")[1]
            else:
                link = a_tag.get("href", "")
            
            date = span_tag.get_text(strip=True).strip("[]") if span_tag else "Unknown"
            
            announcements.append({
                "title": title,
                "link": link,
                "date": date
            })
            
    return announcements

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def notify(new_items):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    for item in new_items:
        msg = (
            f"🔔 *新考试公告发布！*\n\n"
            f"*标题*: {item['title']}\n"
            f"*日期*: {item['date']}\n"
            f"*链接*: [点击查看]({item['link']})"
        )
        print("-" * 30)
        print(msg)
        
        # If Telegram secrets are set, send notification
        if bot_token and chat_id:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": msg,
                    "parse_mode": "Markdown"
                }
                resp = requests.post(url, data=payload, timeout=10)
                if resp.status_code == 200:
                    print("Telegram notification sent successfully!")
                else:
                    print(f"Failed to send Telegram notification: {resp.text}")
            except Exception as e:
                print(f"Error sending Telegram notification: {e}")
        else:
            print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Skipping push notification.")

def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking for updates...")
    html = fetch_announcements()
    if not html:
        return
    
    current_items = parse_announcements(html)
    history = load_history()
    
    # Compare by title and date to identify new ones
    history_keys = {(h["title"], h["date"]) for h in history}
    new_items = [item for item in current_items if (item["title"], item["date"]) not in history_keys]
    
    if new_items:
        print(f"Found {len(new_items)} new announcements!")
        notify(new_items)
        # Update history (keep it simple, just overwrite with current for now or append)
        save_history(current_items)
    else:
        print("No new announcements found.")
        # If history is empty but we found items, save them as initial state
        if not history and current_items:
            print("Initializing history...")
            save_history(current_items)

if __name__ == "__main__":
    main()
