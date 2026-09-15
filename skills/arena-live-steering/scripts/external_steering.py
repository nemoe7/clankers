#!/usr/bin/env python3 -u
"""
External Steering via ntfy.sh - Portable Skill Version
- Random topic generated on first run via generate_topic.py
- Bypasses Arena client entirely
- Works from any browser/phone
- DO NOT USE THIS SKILL IF YOU ARE NOT ON ARENA
"""
import os
import time
import json
import pathlib
import uuid
import urllib.request
import urllib.error

def get_or_create_topic():
    possible_files = [
        pathlib.Path("/home/user/.steering_topic"),
        pathlib.Path("/home/user/STEERING_TOPIC"),
        pathlib.Path("/home/user/arena-live-steering/.topic"),
        pathlib.Path("./.topic"),
        pathlib.Path("./.steering_topic"),
    ]
    for p in possible_files:
        if p.exists():
            try:
                content = p.read_text().strip()
                for token in content.split():
                    if token.startswith("arena-steer-") and len(token) >= 15:
                        return token
            except:
                pass
    topic = f"arena-steer-{uuid.uuid4().hex[:8]}"
    for p in possible_files:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(topic)
        except:
            pass
    return topic

TOPIC = os.environ.get("NTFY_TOPIC") or get_or_create_topic()
STEERING_FILE = os.environ.get("STEERING_FILE", "/home/user/STEERING.md")
LOG_FILE = os.environ.get("LOG_FILE", "/home/user/STEERING_LOG.md")

print(f"""
{'='*70}
🌍 EXTERNAL STEERING ACTIVE - Portable Skill
{'='*70}
Topic (random): {TOPIC}
Publish URL: https://ntfy.sh/{TOPIC}
  -> Open in ANY browser/phone, type, hit Send

Local file: {STEERING_FILE}
DO NOT USE THIS SKILL IF YOU ARE NOT ON ARENA - Arena only
{'='*70}
""", flush=True)

seen_ids = set()
last_since = None

def write_steering(content, msg_id=""):
    try:
        header = "# LIVE STEERING NOTES\n\n## Current Notes:\n\n"
        new_content = header + f"<!-- from ntfy:{msg_id} at {time.strftime('%Y-%m-%d %H:%M:%S')} -->\n" + content + "\n"
        pathlib.Path(STEERING_FILE).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(STEERING_FILE).write_text(new_content, encoding='utf-8')
        with open(LOG_FILE, 'a', encoding='utf-8') as lf:
            lf.write(f"\n\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} [ntfy:{msg_id}] ---\n{content}\n")
        print(f"\n🚨 STEERING RECEIVED at {time.strftime('%H:%M:%S')} [{msg_id}]", flush=True)
        print(content[:2000], flush=True)
        print("-"*60, flush=True)
        up = content.upper()
        if "STOP:" in up:
            print("⚠️  >> STOP directive! Agent must pivot NOW!", flush=True)
        if "PRIORITY:" in up:
            print("⭐ >> PRIORITY directive!", flush=True)
        return True
    except Exception as e:
        print(f"Write failed: {e}", flush=True)
        return False

# Load seen ids from log to avoid reprocessing old messages
if pathlib.Path(LOG_FILE).exists():
    try:
        import re
        log = pathlib.Path(LOG_FILE).read_text(encoding='utf-8', errors='ignore')
        for m in re.findall(r'\[ntfy:([^\]]+)\]', log):
            seen_ids.add(m)
        print(f"Loaded {len(seen_ids)} seen ids, ignoring old messages", flush=True)
    except Exception as e:
        print(f"Could not load log: {e}", flush=True)

print(f"Polling https://ntfy.sh/{TOPIC} every 3s (with 429 backoff)...", flush=True)
print(f"Open https://ntfy.sh/{TOPIC} to send steering notes", flush=True)

while True:
    try:
        url = f"https://ntfy.sh/{TOPIC}/json?poll=1"
        if last_since:
            url += f"&since={last_since}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode('utf-8', errors='ignore')
            for line in data.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                    mid = msg.get("id")
                    message = msg.get("message", "")
                    if not message or not mid or mid in seen_ids:
                        continue
                    seen_ids.add(mid)
                    last_since = mid
                    write_steering(message, msg_id=mid)
                except json.JSONDecodeError:
                    continue
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"Rate limited (429), backing off 10s", flush=True)
            time.sleep(10)
        else:
            print(f"Poll error: {e}", flush=True)
            time.sleep(3)
    except Exception as e:
        print(f"Poll error: {e}", flush=True)
        time.sleep(3)
    else:
        time.sleep(3)
