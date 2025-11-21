# Binance Auto SL/TP (Spot)

Lightweight CustomTkinter GUI to trade spot pairs on Binance with quick market buys, optional stop-loss, and easy percent-based sizing.

## Requirements
- Python 3.11+ (tested with 3.13)
- Binance API keys with spot trading permissions
- Windows (PyInstaller bundle currently built for Windows)

## Setup
```powershell
python -m venv venv
venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt  # if present; otherwise install customtkinter binance python-binance
```

Set environment variables (or use a local `.env` loaded before start):
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`

## Run from source
```powershell
venv\Scripts\python binance_auto_sl_spot.py
```

## Build executable (PyInstaller)
From the repo root:
```powershell
venv\Scripts\python -m PyInstaller BinanceAutoSL.spec
```
Resulting exe: `dist/BinanceAutoSL.exe`.

## Features
- Live price display for the selected USDT pair (updated every second).
- Percent-of-balance calculator writes the rounded base quantity into the order field.
- Quick actions: market buy, market buy + SL, sell all, add SL for free balance, clear SL/TP orders.
- Tooltips across all inputs/buttons to clarify behavior.

## Notes
- Percent sizing works for USDT pairs only.
- Quantities are rounded to exchange `stepSize`; SL prices to `tickSize`.
- Ensure free balances and API permissions are sufficient before trading.
