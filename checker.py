"""Deal Hunter core: check every watched product, compare prices, fire alerts.

State (last prices + last alerts) lives in state.json, which both the PC daemon
and the GitHub Actions checker read/write - so you never get the same alert twice.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import sites
from config import get_settings, get_watchlist


def _load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - corrupted state just starts fresh
            pass
    return {}


def _save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _should_alert(entry: dict, price: int, cooldown_hours: float, now: float) -> bool:
    """Alert for a product the first time, then only when the price makes a new
    low vs the last alerted price - no repeats at the same level (no spam)."""
    last_alert_price = entry.get("last_alert_price")
    if not last_alert_price:
        return True
    return price < last_alert_price


def _build_alert(product: dict, result: dict, last_price: int | None, reason: str) -> dict:
    price = result["price"]
    name = product.get("name") or product.get("id") or "Product"
    title = f"DEAL: {name} at Rs {price:,}"

    lines = [f"{name} is now Rs {price:,}"]
    mrp = result.get("mrp")
    if mrp and mrp > price:
        lines.append(f"MRP Rs {mrp:,}  (-{round((mrp - price) * 100 / mrp)}% off)")
    if last_price and last_price != price:
        lines.append(f"Previous price: Rs {last_price:,}")
    lines.append(f"Why you're getting this: {reason}")

    best = None
    for offer in result.get("card_offers", []):
        lines.append(f"Offer ({offer['bank']}): {offer['text'][:160]}")
        if offer.get("effective") and (best is None or offer["effective"] < best["effective"]):
            best = offer
    if best:
        lines.insert(2, f"Best with your {best['bank']}: approx Rs {best['effective']:,} effective price")

    lines.append("")
    lines.append(f"Buy now: {product['url']}")
    return {"title": title, "body": "\n".join(lines), "url": product["url"], "price": price}


def run_check(settings=None) -> dict:
    """One full pass over the watchlist. Safe to run from PC and cloud."""
    settings = settings or get_settings()
    watchlist = get_watchlist()
    cards = [str(c) for c in watchlist.get("my_cards", []) if str(c).strip()]
    products = watchlist.get("products", [])

    state = _load_state(settings.state_file)
    now = time.time()
    alerts: list[dict] = []
    checked = 0

    for product in products:
        url = product.get("url")
        if not url:
            continue
        pid = str(product.get("id") or url)
        checked += 1
        entry = state.setdefault(pid, {"name": product.get("name") or pid, "url": url})

        try:
            result = sites.check_product(url, cards)
        except Exception as exc:  # noqa: BLE001 - one bad product must not stop the rest
            result = {"price": None, "error": str(exc)[:140]}

        price = result.get("price")
        if not price:
            entry["last_error"] = result.get("error") or "unknown error"
            entry["last_checked_at"] = _now()
            print(f"[skip] {entry['name']}: {entry['last_error']}")
            continue

        entry.pop("last_error", None)
        last_price = entry.get("last_price")
        entry["last_price"] = price
        entry["last_checked_at"] = _now()
        print(f"[ok] {entry['name']}: Rs {price:,}"
              + (f" (was Rs {last_price:,})" if last_price and last_price != price else ""))

        target = product.get("target_price")
        drop_pct = float(product.get("alert_on_drop_pct", settings.default_drop_pct))
        reason = None
        if target and price <= float(target):
            reason = f"below your target price of Rs {int(target):,}"
        elif last_price and last_price > 0:
            drop = (last_price - price) * 100.0 / last_price
            if drop >= drop_pct:
                reason = f"price dropped {drop:.0f}% since the last check"

        if reason and _should_alert(entry, price, settings.cooldown_hours, now):
            alert = _build_alert(product, result, last_price, reason)
            alerts.append(alert)
            entry["last_alert_price"] = price
            entry["last_alert_epoch"] = now
            entry["last_alert_at"] = _now()

        time.sleep(1.0)  # be polite between products/stores

    _save_state(settings.state_file, state)

    from notify import send_all

    sent = send_all(alerts, settings) if alerts else 0
    return {"checked": checked, "alerts": alerts, "sent": sent}
