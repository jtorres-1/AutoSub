import subprocess
import os
import signal
import json
from pathlib import Path

BOT_SCRIPT = os.path.join(os.path.dirname(__file__), "bots", "bot.cjs")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")

def get_stats(user_id):
    stats_path = os.path.join(LOGS_DIR, str(user_id), "stats.json")
    if not os.path.exists(stats_path):
        return {"dms_sent": 0, "replies": 0, "last_run": None}
    try:
        with open(stats_path) as f:
            return json.load(f)
    except:
        return {"dms_sent": 0, "replies": 0, "last_run": None}

def get_log_tail(user_id, lines=50):
    log_path = os.path.join(LOGS_DIR, str(user_id), "bot.log")
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path) as f:
            all_lines = f.readlines()
            return [l.strip() for l in all_lines[-lines:]]
    except:
        return []

def start_bot(user):
    env = os.environ.copy()
    env["AUTOSUB_USER_ID"] = str(user.id)
    env["AUTOSUB_OFFER"] = user.offer_text or ""
    env["AUTOSUB_KEYWORDS"] = user.keywords or ""
    env["AUTOSUB_SUBJECT"] = user.dm_subject or "quick question"
    env["REDDIT_USERNAME"] = user.reddit_username or ""
    env["REDDIT_PASSWORD"] = user.reddit_password or ""
    env["REDDIT_CLIENT_ID"] = user.reddit_client_id or ""
    env["REDDIT_CLIENT_SECRET"] = user.reddit_client_secret or ""
    env["REDDIT_USER_AGENT"] = f"AutoSub/1.0 u/{user.reddit_username}"
    log_dir = os.path.join(LOGS_DIR, str(user.id))
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        ["node", BOT_SCRIPT],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    return proc.pid

def stop_bot(pid):
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        return True
    except Exception as e:
        print(f"Stop bot error: {e}")
        return False

def is_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
