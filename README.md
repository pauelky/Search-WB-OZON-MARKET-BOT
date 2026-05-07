# Market Price Bot

Telegram bot MVP: send a product link or product name, and the bot looks for cheaper available-looking matches on Wildberries, Ozon, and Yandex Market.

## What it does

- Accepts a marketplace product link or a plain query.
- Extracts a readable product name from URL metadata or URL slug.
- Searches configured marketplace providers.
- Sorts candidates by price when a price is available.
- Falls back to marketplace search links when public pages/API responses are blocked.

## Important note

Marketplace public pages often use anti-bot protection and can change without notice. This MVP is built with replaceable providers:

- Wildberries provider tries a public catalog endpoint first.
- Ozon and Yandex Market are searched through lightweight web-search snippets and fallback search URLs.
- Later you can plug in official partner/seller APIs where you have legal access and tokens.

## Run as Telegram bot

### Ubuntu

1. Create a bot with BotFather and copy the token.
2. Create `.env`:

```bash
cp .env.example .env
nano .env
```

3. Run:

```bash
python3 --version
chmod +x run_bot.sh
./run_bot.sh
```

If `python3` is missing:

```bash
sudo apt update
sudo apt install -y python3
```

### Windows PowerShell

1. Create a bot with BotFather and copy the token.
2. Copy `.env.example` to `.env` and fill `TELEGRAM_BOT_TOKEN`.
3. Run:

```powershell
.\run_bot.ps1
```

If you use another Python, run from this folder with:

```powershell
$env:PYTHONPATH="src"
python -m price_bot
```

## Test without Telegram

Ubuntu:

```bash
PYTHONPATH=src python3 -m price_bot "iphone 15 128gb"
PYTHONPATH=src python3 -m unittest discover -s tests
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m price_bot "iphone 15 128gb"
```

Or pass a product URL:

```powershell
$env:PYTHONPATH="src"
python -m price_bot "https://www.ozon.ru/product/..."
```

## Commands

- `/start` or `/help` - show help.
- Send a link or product name - compare prices.

## Tests

Ubuntu:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```
