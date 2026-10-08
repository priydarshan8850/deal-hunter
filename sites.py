"""Fetch product pages and extract price / MRP / bank offers.

Best effort, no login, no API keys. Works for amazon.in, flipkart.com,
myntra/ajio and any page with JSON-LD product data.

Never logs in, never buys - it only reads the public product page.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Cache-Control": "no-cache",
}

_BROWSER_SESSION = None


def _browser_session():
    """Shared Chrome-impersonating session (curl_cffi). Keeps cookies between
    calls, which is what gets past Amazon's bot wall on product pages."""
    global _BROWSER_SESSION
    if _BROWSER_SESSION is None:
        from curl_cffi import requests as curl_requests

        _BROWSER_SESSION = curl_requests.Session(impersonate="chrome")
    return _BROWSER_SESSION


def detect_site(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "amazon." in host:
        return "amazon"
    if "flipkart." in host:
        return "flipkart"
    if "myntra." in host or "ajio." in host:
        return "myntra"
    return "generic"


def _blank() -> dict:
    return {"price": None, "mrp": None, "in_stock": True, "card_offers": [], "error": None, "site": ""}


def _num(text) -> int | None:
    cleaned = re.sub(r"[^\d]", "", str(text or ""))
    return int(cleaned) if cleaned else None


def _money(text) -> float | None:
    """Parse money text like '17.00' or '3,000.00' into a float."""
    cleaned = re.sub(r"[^\d.]", "", str(text or ""))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _first(patterns, html: str) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, html, re.S)
        if match:
            value = _num(match.group(1))
            if value:
                return value
    return None


# --------------------------------------------------------------------------
# store parsers
# --------------------------------------------------------------------------

def parse_amazon(html: str, url: str = "") -> dict:
    out = _blank()
    out["price"] = _first([
        r'class="a-price-whole">\s*([\d,]+)',
        r'id="priceblock_dealprice"[^>]*>\s*(?:₹|Rs\.?)\s*([\d,]+)',
        r'id="priceblock_ourprice"[^>]*>\s*(?:₹|Rs\.?)\s*([\d,]+)',
        r'"priceAmount"\s*:\s*([\d.]+)',
    ], html)
    out["mrp"] = _first([
        r'class="a-text-price"[^>]*>\s*<span[^>]*>(?:₹|Rs\.?)\s*([\d,]+)',
        r'(?:M\.R\.P\.?|MRP)[^0-9₹]{0,25}(?:₹|Rs\.?)?\s*([\d,]{3,})',
    ], html)
    lower = html.lower()
    if "currently unavailable" in lower or "out of stock" in lower and not out["price"]:
        out["in_stock"] = False
    if not out["price"]:
        out["error"] = "price not found (bot-check page or product unavailable)"
    return out


def parse_flipkart(html: str, url: str = "") -> dict:
    out = _blank()
    out["price"] = _first([
        r'"finalPrice"\s*:\s*(\d+)',
        r'"fsp"\s*:\s*(\d+)',
        r'"nepPrice"\s*:\s*(\d+)',
        r'"finalPrice"\s*:\s*\{\s*"value"\s*:\s*([\d.]+)',
        r'"@type"\s*:\s*"Product".{0,4000}?"price"\s*:\s*"?([\d.]+)',
    ], html)
    out["mrp"] = _first([
        r'"mrp"\s*:\s*(\d+)',
        r'"mrp"\s*:\s*\{\s*"value"\s*:\s*([\d.]+)',
        r'"listPrice"\s*:\s*(\d+)',
    ], html)
    if not out["price"]:
        out["error"] = "price not found"
    return out


def parse_myntra(html: str, url: str = "") -> dict:
    out = _blank()
    out["price"] = _first([
        r'"discountedPrice"\s*:\s*(\d+)',
        r'"price"\s*:\s*\{\s*"discounted"\s*:\s*(\d+)',
        r'"discounted_price"\s*:\s*(\d+)',
    ], html)
    out["mrp"] = _first([
        r'"mrp"\s*:\s*(\d+)',
        r'"price"\s*:\s*\{\s*"mrp"\s*:\s*(\d+)',
    ], html)
    if not out["price"]:
        out["error"] = "price not found"
    return out


def parse_generic(html: str, url: str = "") -> dict:
    out = _blank()
    out["price"] = _first([
        r'"@type"\s*:\s*"Product".{0,4000}?"price"\s*:\s*"?([\d.]+)',
        r'"price"\s*:\s*"?\s*([\d,]+\.?\d*)',
        r'(?:₹|Rs\.?)\s*([\d,]{2,})',
    ], html)
    out["mrp"] = _first([
        r'"@type"\s*:\s*"Product".{0,4000}?"(?:listPrice|highPrice|mrp)"\s*:\s*"?([\d.]+)',
    ], html)
    if not out["price"]:
        out["error"] = "price not found"
    return out


# --------------------------------------------------------------------------
# bank-offer detection (uses only the bank NAMES the user configures)
# --------------------------------------------------------------------------

def html_to_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text)


def estimate_effective(price: int, offer_text: str) -> int | None:
    """Estimate the price you would pay with that bank offer (best effort)."""
    pct = re.search(r"(\d{1,2}(?:\.\d)?)\s*%", offer_text)
    if pct:
        percent = float(pct.group(1))
        if percent <= 0 or percent > 50:
            return None
        discount = price * percent / 100.0
        cap = re.search(
            r"(?:up to|upto|max(?:imum)?)[^0-9]{0,14}(?:₹|Rs\.?)?\s*([\d,]{2,}(?:\.\d{1,2})?)",
            offer_text, re.I,
        )
        if cap:
            cap_amount = _money(cap.group(1))
            if cap_amount:
                discount = min(discount, cap_amount)
        return int(round(price - discount))
    flat = re.search(
        r"(?:₹|Rs\.?)\s*([\d,]{1,6}(?:\.\d{1,2})?)\s*(?:off|discount|cashback)",
        offer_text, re.I,
    )
    if flat:
        amount = _money(flat.group(1)) or 0
        if 0 < amount < price:  # ignore caps bigger than the price (min-spend offers)
            return int(round(price - amount))
    return None


_NOISE_RE = re.compile(
    r"(?:Previous page|Full content visible|double tap to read brief content|"
    r"brief content|bank offers?|offers?|tabs?|tap|\d+\s*offers?)\b[.,:;\s-]*",
    re.I,
)


def _clean_snippet(raw: str) -> str:
    raw = _NOISE_RE.sub(" ", raw)
    return re.sub(r"\s+", " ", raw).strip(" .,;:-")


def find_card_offers(html: str, cards: list[str], limit: int = 3) -> list[dict]:
    """Find offers mentioning the user's banks. cards = ['HDFC', 'ICICI', ...]."""
    if not cards:
        return []
    text = html_to_text(html)
    found: list[dict] = []
    seen: set[str] = set()
    for card in cards:
        key = card.strip().split()[0] if card.strip() else ""
        if not key:
            continue
        for match in re.finditer(re.escape(key), text, re.I):
            # Anchor the snippet at the nearest price/percent before the bank
            # name, and stop shortly after it - then strip page clutter.
            window_start = max(0, match.start() - 150)
            pre = text[window_start:match.start()]
            amounts = list(re.finditer(r"(?:₹|Rs\.?)\s*[\d,]+(?:\.\d{1,2})?", pre))
            if amounts:  # nearest price before the bank name anchors the snippet
                start = window_start + amounts[-1].start()
            else:
                start = max(0, match.start() - 60)
            back = 0
            while start > 0 and text[start - 1] not in " .;:!?" and back < 15:
                start -= 1  # snap backwards to a word boundary
                back += 1
            post = text[match.end(): match.end() + 120]
            tail = re.search(r"\s\S*$", post)
            if tail:
                post = post[:tail.start()]
            stop = re.search(r"Cashback Upto|Bank Offer|Partner|Discount Offer|₹|Rs\.?\s?[\d,]", post, re.I)
            if stop:  # never bleed into the next offer's text
                post = post[:stop.start()]
            snippet = _clean_snippet(text[start:match.end()] + post)
            snippet = re.sub(r"(?:Cashback|Upto|discount on|save)\s*$", "", snippet, flags=re.I)
            snippet = snippet.strip(" .,;:-")[:220].strip()
            if not snippet or not re.search(r"\d+\s*%|(?:₹|Rs\.?)\s*[\d,]+", snippet):
                continue
            if not re.search(r"off|discount|cashback|instant|save", snippet, re.I):
                continue
            low = snippet.lower()
            if low in seen:
                continue
            seen.add(low)
            found.append({"bank": key, "text": snippet})
            break  # one snippet per bank is enough for a clean alert
    return found[:limit]


# --------------------------------------------------------------------------

def fetch(url: str) -> tuple[int, str]:
    """Fetch a page. Tries a Chrome-impersonating client first (beats bot
    walls on Amazon etc.), falls back to plain httpx. Raises on total failure."""
    problems: list[str] = []

    try:
        resp = _browser_session().get(url, headers=BROWSER_HEADERS, timeout=30, allow_redirects=True)
        status, text = resp.status_code, resp.text or ""
        if status == 200 and len(text) >= 5000:
            return status, text
        problems.append(f"browser client: HTTP {status} ({len(text)} bytes)")
    except Exception as exc:  # noqa: BLE001 - try the next client
        problems.append(f"browser client: {str(exc)[:90]}")

    try:
        import httpx

        resp = httpx.get(url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=30)
        status, text = resp.status_code, resp.text or ""
        if status == 200 and len(text) >= 5000:
            return status, text
        problems.append(f"httpx: HTTP {status} ({len(text)} bytes)")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"httpx: {str(exc)[:90]}")

    raise RuntimeError(" | ".join(problems))


def check_product(url: str, cards: list[str] | None = None) -> dict:
    """Fetch + parse one product URL. Returns a result dict, never raises."""
    cards = cards or []
    site = detect_site(url)
    try:
        status, html = fetch(url)
    except Exception as exc:  # noqa: BLE001 - report, never crash the whole run
        out = _blank()
        out["site"] = site
        out["error"] = f"fetch failed: {str(exc)[:120]}"
        return out
    if status >= 400:
        out = _blank()
        out["site"] = site
        out["error"] = f"HTTP {status}"
        return out

    if site == "amazon":
        out = parse_amazon(html, url)
    elif site == "flipkart":
        out = parse_flipkart(html, url)
    elif site == "myntra":
        out = parse_myntra(html, url)
    else:
        out = parse_generic(html, url)

    out["site"] = site
    offers = find_card_offers(html, cards)
    for offer in offers:
        if out.get("price"):
            offer["effective"] = estimate_effective(out["price"], offer["text"])
    out["card_offers"] = offers
    return out
