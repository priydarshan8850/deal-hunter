"""Deal Hunter daemon: watches prices while this PC is on.

Every CHECK_INTERVAL_MINUTES it checks all watched products, fires alerts
(Windows popup + email), and pushes state.json to GitHub so the cloud checker
never sends you the same alert again.

Run: double-click deals_watch.bat  (stop with Ctrl+C or close the window)
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 - optional
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for _noisy in ("httpx", "httpcore", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, text=True, timeout=180
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()[:300]}")
    return result


def main() -> int:
    from checker import run_check
    from config import get_settings

    settings = get_settings()
    print(f"Deal Hunter watching every {settings.check_interval_minutes} min. Stop with Ctrl+C.")
    print(f"Alerts: email={'on' if settings.email_enabled else 'off'} | windows popup=on | "
          f"telegram={'on' if settings.telegram_token else 'off'}")

    while True:
        stamp = time.strftime("%H:%M:%S")
        try:
            if settings.git_sync:
                git("pull", "--rebase", "--autostash", check=False)

            result = run_check(settings)
            print(f"[{stamp}] checked {result['checked']} products, "
                  f"{len(result['alerts'])} alerts, {result['sent']} delivered")
            for alert in result["alerts"]:
                print(f"    * {alert['title']}")

            if settings.git_sync:
                git("add", "state.json", check=False)
                commit = git("commit", "-m", "state: deal check", check=False)
                if commit.returncode == 0:
                    for _ in range(3):
                        if git("push", check=False).returncode == 0:
                            break
                        git("pull", "--rebase", "--autostash", check=False)
        except Exception as exc:  # noqa: BLE001 - the daemon must never die
            print(f"[{stamp}] cycle error: {exc}")
        time.sleep(max(5, settings.check_interval_minutes) * 60)


if __name__ == "__main__":
    sys.exit(main())
