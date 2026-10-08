"""One deal check - used by the PC (check_now.bat) and by GitHub Actions."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 - optional
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
for _noisy in ("httpx", "httpcore", "hpack"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def main() -> int:
    from checker import run_check

    result = run_check()
    print(f"Checked {result['checked']} products | {len(result['alerts'])} alerts | "
          f"{result['sent']} delivered")
    for alert in result["alerts"]:
        print(f"ALERT: {alert['title']}")
        print(alert["body"])
        print("-" * 60)
    return 0  # never fail the workflow because one store blocked us


if __name__ == "__main__":
    sys.exit(main())
