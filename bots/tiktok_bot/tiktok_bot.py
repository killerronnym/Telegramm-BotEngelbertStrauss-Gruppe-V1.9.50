import asyncio
import time
import requests
import json
import os
import sys
import sqlite3
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

# Pfade absolut bestimmen
# Datei ist in bots/tiktok_bot/tiktok_bot.py
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '../..'))
DB_PATH = os.path.join(PROJECT_ROOT, 'instance', 'app.db')

try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import (
        ConnectEvent,
        DisconnectEvent,
        CommentEvent,
        JoinEvent,
        GiftEvent,
        LikeEvent,
        ShareEvent,
        FollowEvent,
    )
except ImportError:
    print("Error: TikTokLive library not found. Please install it using 'pip install TikTokLive'")
    sys.exit(1)

# =========================
# CONFIG LOAD DIRECTLY FROM DB
# =========================

def get_config_from_db(bot_name):
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at: {DB_PATH}")
        return {}
        
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT config_json FROM bot_settings WHERE bot_name = ?", (bot_name,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception as e:
        print(f"Error reading DB ({bot_name}): {e}")
    return {}

def load_config():
    # Load Telegram Bot Token from 'id_finder' config
    id_finder_config = get_config_from_db("id_finder")
    telegram_token = id_finder_config.get("bot_token")

    # Load TikTok Bot specific config
    tiktok_config = get_config_from_db("tiktok_bot")
    
    return {
        "TELEGRAM_BOT_TOKEN": telegram_token,
        "TELEGRAM_CHAT_ID": tiktok_config.get("telegram_chat_id"),
        "TELEGRAM_TOPIC_ID": tiktok_config.get("telegram_topic_id"),
        "TARGET_UNIQUE_ID": tiktok_config.get("target_unique_id"),
        "WATCH_HOSTS": tiktok_config.get("watch_hosts", []),
        "RETRY_OFFLINE_SECONDS": tiktok_config.get("retry_offline_seconds", 60),
        "ALERT_COOLDOWN_SECONDS": tiktok_config.get("alert_cooldown_seconds", 600),
        "MAX_CONCURRENT_LIVES": tiktok_config.get("max_concurrent_lives", 3),
        "IS_ACTIVE": tiktok_config.get("is_active", False),
        "MESSAGE_TEMPLATE_SELF": tiktok_config.get("message_template_self", "🔴 {target} ist jetzt LIVE!\n\n🔗 {url}"),
        "MESSAGE_TEMPLATE_PRESENCE": tiktok_config.get("message_template_presence", "👀 {target} wurde in einem TikTok-Live gesehen!\n\n🎥 Host: @{host}\n📌 Event: {event}\n🔗 {url}")
    }

def tg_send(token: str, chat_id: str, topic_id: str, text: str) -> None:
    if not token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False,
    }
    
    if topic_id:
        try:
            payload["message_thread_id"] = int(topic_id)
        except:
            pass

    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

@dataclass
class AlertState:
    last_sent: Dict[Tuple[str, str], float]
    cooldown: int

    def can_send(self, host: str, target: str) -> bool:
        k = (host.lower(), target.lower())
        now = time.time()
        last = self.last_sent.get(k, 0.0)
        return (now - last) >= self.cooldown

    def mark_sent(self, host: str, target: str) -> None:
        self.last_sent[(host.lower(), target.lower())] = time.time()


def live_url(host_unique_id: str) -> str:
    return f"https://www.tiktok.com/@{host_unique_id}/live"


def norm(s: Optional[str]) -> str:
    return (s or "").strip().lstrip("@").lower()


async def watch_one_host(host_unique_id: str, target_unique_id: str, alert_state: AlertState, sem: asyncio.Semaphore) -> None:
    host_unique_id = norm(host_unique_id)
    target = norm(target_unique_id)
    
    if not host_unique_id or not target:
        return

    is_self_monitoring = (host_unique_id == target)

    while True:
        config = load_config()
        if not config.get("IS_ACTIVE"):
            await asyncio.sleep(60)
            continue

        async with sem:
            client = TikTokLiveClient(unique_id=host_unique_id)

            def maybe_alert(event_name: str, user_unique_id: str) -> None:
                u = norm(user_unique_id)
                if not is_self_monitoring and u != target:
                    return

                if not alert_state.can_send(host_unique_id, target):
                    return

                template = config["MESSAGE_TEMPLATE_SELF"] if is_self_monitoring else config["MESSAGE_TEMPLATE_PRESENCE"]

                try:
                    msg = template.format(
                        target=target_unique_id,
                        host=host_unique_id,
                        event=event_name,
                        url=live_url(host_unique_id)
                    )
                except Exception as e:
                    print(f"[{host_unique_id}] Error formatting message: {e}")
                    msg = f"Meldung: {target_unique_id} @ {host_unique_id}. Link: {live_url(host_unique_id)}"
                
                tg_send(config["TELEGRAM_BOT_TOKEN"], config["TELEGRAM_CHAT_ID"], config["TELEGRAM_TOPIC_ID"], msg)
                alert_state.mark_sent(host_unique_id, target)

            @client.on(ConnectEvent)
            async def on_connect(_: ConnectEvent):
                print(f"[{host_unique_id}] ✅ verbunden (Host ist live)")
                if is_self_monitoring:
                    maybe_alert("Self-Live", target)

            @client.on(DisconnectEvent)
            async def on_disconnect(_: DisconnectEvent):
                print(f"[{host_unique_id}] ❌ getrennt")

            @client.on(JoinEvent)
            async def on_join(event: JoinEvent):
                maybe_alert("Join", getattr(event.user, "unique_id", ""))

            @client.on(CommentEvent)
            async def on_comment(event: CommentEvent):
                maybe_alert("Comment", getattr(event.user, "unique_id", ""))

            @client.on(GiftEvent)
            async def on_gift(event: GiftEvent):
                maybe_alert("Gift", getattr(event.user, "unique_id", ""))

            @client.on(LikeEvent)
            async def on_like(event: LikeEvent):
                maybe_alert("Like", getattr(event.user, "unique_id", ""))

            @client.on(ShareEvent)
            async def on_share(event: ShareEvent):
                maybe_alert("Share", getattr(event.user, "unique_id", ""))

            @client.on(FollowEvent)
            async def on_follow(event: FollowEvent):
                maybe_alert("Follow", getattr(event.user, "unique_id", ""))

            try:
                await client.start()
            except Exception:
                pass
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        await asyncio.sleep(config["RETRY_OFFLINE_SECONDS"])


async def main():
    print("TikTok Live Monitor starting...")
    config = load_config()
    
    if not config["TELEGRAM_BOT_TOKEN"]:
        # Token-Suche in Alternativen
        for name in ['id_finder', 'invite', 'id_finder_bot', 'invite_bot']:
            alt_config = get_config_from_db(name)
            if alt_config.get('bot_token'):
                config["TELEGRAM_BOT_TOKEN"] = alt_config.get('bot_token')
                break
        
        if not config["TELEGRAM_BOT_TOKEN"]:
            print("Fatal Error: No Telegram Bot Token found in database.")
            return

    print(f"Database: {DB_PATH}")
    print(f"Target: {config['TARGET_UNIQUE_ID']}")
    
    alert_state = AlertState(last_sent={}, cooldown=config["ALERT_COOLDOWN_SECONDS"])
    sem = asyncio.Semaphore(config["MAX_CONCURRENT_LIVES"])

    tasks = []
    for h in config["WATCH_HOSTS"]:
        tasks.append(asyncio.create_task(watch_one_host(h, config["TARGET_UNIQUE_ID"], alert_state, sem)))
    
    if config["TARGET_UNIQUE_ID"]:
        tasks.append(asyncio.create_task(watch_one_host(config["TARGET_UNIQUE_ID"], config["TARGET_UNIQUE_ID"], alert_state, sem)))
    
    if not tasks:
        print("Info: Keine Hosts eingetragen. Warte auf Konfiguration...")
        while not tasks:
            await asyncio.sleep(30)
            return await main()

    print(f"Monitoring {len(tasks)} paths.")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
