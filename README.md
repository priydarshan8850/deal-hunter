# Deal Hunter

Watches product prices on Amazon / Flipkart / Myntra (and any store) and pings
you the moment a discount hits your target price - by **email** and **Windows
notification** - with a one-tap **Buy** link.

Runs in two places (same code, shared state):

| Where | When | How |
|---|---|---|
| Your PC | when it's on | double-click `deals_watch.bat` (checks every 30 min) |
| GitHub Actions cloud | always, even PC off | automatic every ~30 min (free) |

## Quick start

1. **Add products** to `watchlist.json`:
   - paste product page URLs (Amazon / Flipkart / Myntra)
   - set `target_price` (alert when price goes below it)
   - add your bank names to `my_cards` (names only, e.g. `"HDFC"`, `"ICICI"` -
     **never card numbers**) so alerts highlight the best bank offer for you
2. **Enable email alerts** - open `.env` and fill `SMTP_USER` / `SMTP_PASS` /
   `EMAIL_TO` (Gmail app-password steps are written inside the file).
3. **Run it**: double-click `deals_watch.bat`, or `check_now.bat` for a
   single instant check.

## How buying works (important)

This tool never stores your card/bank details and never pays for you - no
legitimate tool does that, and stores ban auto-checkout bots. Save your
card/UPI inside the store itself; the alert's **Buy** link opens the product
page where checkout is one tap away.

## Notes

- Prices are read from public pages - occasionally a store blocks a check;
  it's skipped and retried next cycle (`state.json` remembers everything).
- Alert rules: below `target_price`, or any drop >= `alert_on_drop_pct`
  (default 5%). One alert per product per `cooldown_hours` unless the price
  drops further.
- Optional Telegram alerts: create a bot chat id and fill the `TELEGRAM_*`
  lines in `.env` (the news bot's token works, but use a separate chat).
