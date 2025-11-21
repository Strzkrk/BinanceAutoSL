import os
import sys
from decimal import Decimal
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

# =========================
# SIMPLE TOOLTIP HELPER
# =========================
class ToolTip:
    def __init__(self, widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay  # ms
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

        widget.bind("<Enter>", self._enter)
        widget.bind("<Leave>", self._leave)
        widget.bind("<Motion>", self._motion)
    def _enter(self, event=None):
        self._schedule()
    def _leave(self, event=None):
        self._unschedule()
        self._hide_tip()
    def _motion(self, event):
        self.x = event.x_root + 12
        self.y = event.y_root + 12
    def _schedule(self):
        self._unschedule()
        self.id = self.widget.after(self.delay, self._show_tip)
    def _unschedule(self):
        if self.id is not None:
            self.widget.after_cancel(self.id)
            self.id = None
    def _show_tip(self):
        if self.tipwindow or not self.text:
            return

        x = self.x or (self.widget.winfo_rootx() + 20)
        y = self.y or (self.widget.winfo_rooty() + 20)

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)  # keep tooltip above all app windows
        tw.lift()
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#333333",
            foreground="#ffffff",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10)
        )
        label.pack(ipadx=0, ipady=0)
    def _hide_tip(self):
        tw = self.tipwindow
        if tw is not None:
            tw.destroy()
            self.tipwindow = None
def add_tooltip(widget, text: str):
    ToolTip(widget, text)

# =========================
# TOP-SYMBOLE (Dropdown)
# =========================
def get_all_usdt_symbols() -> list[str]:
    """
    Liefert alle Binance Handelspaare, die mit 'USDT' enden.
    Sortiert alphabetisch.
    """
    try:
        tickers = client.get_all_tickers()
    except Exception as e:
        log(f"[ERROR] get_all_tickers: {e}")
        return []

    symbols = sorted([
        t["symbol"]
        for t in tickers
        if t["symbol"].endswith("USDT")
    ])

    return symbols

# =========================
# ENV / CLIENT
# =========================
def get_env_or_die(name: str) -> str:
    value = os.getenv(name)
    if not value:
        messagebox.showerror(
            "Missing Environment Variable",
            f"{name} is not set.\n\nSet it as environment variable "
            f"(e.g. with setx) and restart the program."
        )
        sys.exit(1)
    return value
def create_client() -> Client: 
    api_key = get_env_or_die("BINANCE_API_KEY") 
    api_secret = get_env_or_die("BINANCE_API_SECRET") 
    return Client(api_key, api_secret) 
client: Client | None = None # will be set later

# =========================
# HELPER: ROUNDING / FILTERS
# =========================
def round_down_step(value: Decimal, step: Decimal) -> Decimal:
    """
    Round value down to the next multiple of step.
    Example: value=1.234, step=0.01 -> 1.23
    """
    if step <= 0:
        return value
    return (value // step) * step
def fmt_decimal(val: Decimal) -> str:
    """
    Render a Decimal without unnecessary trailing zeros (e.g. 0.01000000 -> 0.01).
    """
    q = val.normalize()
    s = format(q, "f")
    s = s.rstrip("0").rstrip(".")
    return s or "0"
def get_symbol_info_cached(symbol: str) -> dict:
    info = client.get_symbol_info(symbol)
    if not info:
        raise ValueError(f"Symbol not found: {symbol}")
    return info
def get_filters(symbol: str):
    """
    Return (tick_size, step_size, min_notional) as Decimals.
    """
    info = get_symbol_info_cached(symbol)
    filters = info.get("filters", [])

    tick_size = Decimal("0.01")
    step_size = Decimal("0.00000001")
    min_notional = Decimal("0")

    for f in filters:
        ftype = f.get("filterType")
        if ftype == "PRICE_FILTER":
            tick_size = Decimal(f["tickSize"])
        elif ftype == "LOT_SIZE":
            step_size = Decimal(f["stepSize"])
        elif ftype == "MIN_NOTIONAL":
            min_notional = Decimal(f["minNotional"])

    return tick_size, step_size, min_notional

# =========================
# LOG & ACCOUNT
# =========================
def log(msg: str) -> None:
    log_text.configure(state="normal")
    log_text.insert("end", msg + "\n")
    log_text.see("end")
    log_text.configure(state="disabled")
def get_usdt_balance() -> Decimal:
    try:
        bal = client.get_asset_balance(asset="USDT")
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_asset_balance(USDT): {e}")
        return Decimal("0")
    free_str = bal.get("free", "0")
    try:
        return Decimal(free_str)
    except Exception:
        return Decimal("0")
def get_total_usdt_value() -> Decimal:
    """
    Rough estimate of total account value in USDT.
    """
    try:
        account = client.get_account()
        tickers = client.get_all_tickers()
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_account/get_all_tickers: {e}")
        return Decimal("0")

    price_map = {t["symbol"]: Decimal(t["price"]) for t in tickers}
    total = Decimal("0")

    for b in account.get("balances", []):
        asset = b.get("asset")
        free_amt = Decimal(b.get("free", "0"))
        locked_amt = Decimal(b.get("locked", "0"))
        amount = free_amt + locked_amt
        if amount <= 0:
            continue

        if asset == "USDT":
            total += amount
            continue

        symbol = f"{asset}USDT"
        if symbol in price_map:
            total += amount * price_map[symbol]

    return total
def refresh_account_labels():
    usdt = get_usdt_balance()
    total = get_total_usdt_value()
    label_usdt.configure(text=f"free: {usdt:.0f}")
    label_total.configure(text=f"total: {total:.0f} USDT")

# =========================
# TRADING FUNCTIONS
# =========================
def buy_spot(symbol: str, qty_str: str) -> None:
    try:
        qty = Decimal(qty_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid quantity: {qty_str}")
        return

    if qty <= 0:
        messagebox.showerror("Error", "Quantity must be > 0.")
        return

    # Filter holen und Menge auf stepSize runden
    try:
        _, step_size, _ = get_filters(symbol)
    except Exception as e:
        log(f"[ERROR] Symbol info: {e}")
        messagebox.showerror("Error", str(e))
        return

    qty_rounded = round_down_step(qty, step_size)
    if qty_rounded <= 0:
        messagebox.showerror("Error", "Rounded quantity is 0. Increase quantity.")
        return

    log(f"[INFO] Market BUY {symbol}, qty {qty_rounded} ...")

    try:
        order = client.order_market_buy(
            symbol=symbol,
            quantity=float(qty_rounded)
        )
        log(f"[OK] BUY OrderId={order.get('orderId')} Status={order.get('status')}")
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] Market-Buy failed: {e}")
        messagebox.showerror("API Error", str(e))
def buy_spot_with_sl(symbol: str, qty_str: str,
                     sl_trigger_percent_str: str,
                     sl_limit_percent_str: str) -> None:
    # parse quantity
    try:
        qty = Decimal(qty_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid quantity: {qty_str}")
        return

    if qty <= 0:
        messagebox.showerror("Error", "Quantity must be > 0.")
        return

    # parse trigger %
    try:
        sl_trigger_percent = Decimal(sl_trigger_percent_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid SL trigger %: {sl_trigger_percent_str}")
        return

    if sl_trigger_percent <= 0:
        messagebox.showerror("Error", "SL trigger % must be > 0.")
        return

    # parse limit %
    try:
        sl_limit_percent = Decimal(sl_limit_percent_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid SL limit %: {sl_limit_percent_str}")
        return

    if sl_limit_percent <= 0:
        messagebox.showerror("Error", "SL limit % must be > 0.")
        return

    # optional: ensure limit deeper than trigger
    if sl_limit_percent < sl_trigger_percent:
        if not messagebox.askyesno(
            "Warning",
            "SL limit % is smaller than SL trigger %.\n"
            "Usually the limit should be >= trigger (deeper).\n\nContinue anyway?"
        ):
            return

    sl_trigger_factor = sl_trigger_percent / Decimal("100")
    sl_limit_factor = sl_limit_percent / Decimal("100")

    log(f"[INFO] Market BUY {symbol}, qty {qty}, "
        f"SL trigger -{sl_trigger_percent}%, SL limit -{sl_limit_percent}% ...")

    # filters
    try:
        tick_size, step_size, min_notional = get_filters(symbol)
    except Exception as e:
        log(f"[ERROR] Symbol info: {e}")
        messagebox.showerror("Error", str(e))
        return

    qty_rounded = round_down_step(qty, step_size)
    if qty_rounded <= 0:
        messagebox.showerror("Error", "Rounded quantity is 0. Increase quantity.")
        return

    # 1) Market BUY
    try:
        buy_order = client.order_market_buy(
            symbol=symbol,
            quantity=float(qty_rounded)
        )
        log(f"[OK] BUY OrderId={buy_order.get('orderId')} Status={buy_order.get('status')}")
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] Market-Buy failed: {e}")
        messagebox.showerror("API Error", str(e))
        return

    fills = buy_order.get("fills", [])
    if not fills:
        log("[ERROR] No fills -> cannot determine execution price.")
        messagebox.showerror("Error", "No fills in buy order.")
        return

    # weighted avg price
    total_amount = Decimal("0")
    total_quote = Decimal("0")
    for f in fills:
        price = Decimal(f["price"])
        q = Decimal(f["qty"])
        total_amount += q
        total_quote += price * q

    if total_amount == 0:
        log("[ERROR] total_amount == 0 – something went wrong.")
        messagebox.showerror("Error", "total_amount == 0.")
        return

    avg_price = total_quote / total_amount
    log(f"[INFO] Avg execution price: {avg_price}")

    # 2) SL prices
    raw_stop = avg_price * (Decimal("1") - sl_trigger_factor)
    raw_limit = avg_price * (Decimal("1") - sl_limit_factor)

    raw_stop = round_down_step(raw_stop, tick_size)
    raw_limit = round_down_step(raw_limit, tick_size)

    # Stop = näher am Markt, Limit = weiter unten
    sl_stop_price = max(raw_stop, raw_limit)
    sl_limit_price = min(raw_stop, raw_limit)

    # 3) SL-MENGE: echten freien Bestand nach dem Buy nehmen
    try:
        info = get_symbol_info_cached(symbol)
        base_asset = info.get("baseAsset")
        if not base_asset:
            messagebox.showerror("Error", f"baseAsset not found for {symbol}.")
            return
        balance = client.get_asset_balance(asset=base_asset)
        free_amount = Decimal(balance.get("free", "0"))
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_asset_balance for SL qty: {e}")
        messagebox.showerror("API Error", str(e))
        return
    except Exception as e:
        messagebox.showerror("Error", str(e))
        return

    sl_qty = round_down_step(free_amount, step_size)
    if sl_qty <= 0:
        messagebox.showerror("Error", "Free balance for SL is 0 after fees/rounding.")
        log("[ERROR] SL quantity after balance/fees is 0.")
        return

    log("[INFO] Place Stop-Loss-Limit:")
    log(f"       Trigger (stopPrice): {sl_stop_price}")
    log(f"       Limit   (price)    : {sl_limit_price}")
    log(f"       Qty                 : {sl_qty}")

    # 4) SL order
    try:
        sl_order = client.create_order(
            symbol=symbol,
            side="SELL",
            type="STOP_LOSS_LIMIT",
            timeInForce="GTC",
            quantity=float(sl_qty),
            price=str(sl_limit_price),
            stopPrice=str(sl_stop_price),
            newOrderRespType="FULL"
        )
        log(f"[OK] SL OrderId={sl_order.get('orderId')} Status={sl_order.get('status')}")
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] Stop-Loss order failed: {e}")
        messagebox.showerror("API Error", str(e))
def cancel_sl_orders(symbol: str) -> int:
    """
    Cancel SL/TP orders for a single symbol.
    """
    try:
        open_orders = client.get_open_orders(symbol=symbol)
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_open_orders: {e}")
        messagebox.showerror("API Error", str(e))
        return 0

    cancel_types = {"STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}
    count = 0

    for o in open_orders:
        if o.get("type") in cancel_types:
            try:
                client.cancel_order(symbol=symbol, orderId=o["orderId"])
                log(f"[OK] Canceled SL/TP order: Id={o['orderId']} Type={o['type']}")
                count += 1
            except (BinanceAPIException, BinanceRequestException) as e:
                log(f"[ERROR] cancel_order {o['orderId']}: {e}")

    if count == 0:
        log("[INFO] No SL/TP orders for this symbol.")
    return count
def cancel_all_sl_orders() -> int:
    """
    Cancel all SL/TP orders on the entire account.
    (nicht genutzt, kann aber bleiben)
    """
    try:
        open_orders = client.get_open_orders()
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_open_orders(all): {e}")
        messagebox.showerror("API Error", str(e))
        return 0

    cancel_types = {"STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}
    count = 0

    for o in open_orders:
        if o.get("type") in cancel_types:
            symbol = o.get("symbol")
            try:
                client.cancel_order(symbol=symbol, orderId=o["orderId"])
                log(f"[OK] Canceled SL/TP order: {symbol} Id={o['orderId']} Type={o['type']}")
                count += 1
            except (BinanceAPIException, BinanceRequestException) as e:
                log(f"[ERROR] cancel_order {symbol} {o['orderId']}: {e}")

    if count == 0:
        log("[INFO] No SL/TP orders on account.")
    else:
        log(f"[INFO] Cleared {count} SL/TP orders.")
    return count
def sell_all(symbol: str) -> None:
    log(f"[INFO] Cancel SL/TP orders for {symbol} ...")
    cancel_sl_orders(symbol)

    try:
        info = get_symbol_info_cached(symbol)
    except Exception as e:
        log(f"[ERROR] Symbol info: {e}")
        messagebox.showerror("Error", str(e))
        return

    base_asset = info.get("baseAsset")
    if not base_asset:
        messagebox.showerror("Error", f"baseAsset not found for {symbol}.")
        return

    try:
        balance = client.get_asset_balance(asset=base_asset)
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_asset_balance({base_asset}): {e}")
        messagebox.showerror("API Error", str(e))
        return

    free_str = balance.get("free", "0")
    try:
        free_amount = Decimal(free_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid balance: {free_str}")
        return

    if free_amount <= 0:
        log(f"[INFO] No free balance of {base_asset} to sell.")
        return

    tick_size, step_size, min_notional = get_filters(symbol)
    sell_qty = round_down_step(free_amount, step_size)
    if sell_qty <= 0:
        messagebox.showerror("Error", "Rounded sell quantity is 0.")
        return

    log(f"[INFO] Market SELL all: {fmt_decimal(sell_qty)} {base_asset} ...")

    try:
        order = client.order_market_sell(
            symbol=symbol,
            quantity=float(sell_qty)
        )
        log(f"[OK] SELL OrderId={order.get('orderId')} Status={order.get('status')}")
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] Market-Sell failed: {e}")
        messagebox.showerror("API Error", str(e))
def add_sl_for_free(symbol: str,
                    sl_trigger_percent_str: str,
                    sl_limit_percent_str: str) -> None:
    """
    Setzt eine SL-Order für den gesamten freien Bestand des Base-Coins
    des gewählten Symbols (ohne neuen Buy).
    """
    # parse trigger %
    try:
        sl_trigger_percent = Decimal(sl_trigger_percent_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid SL trigger %: {sl_trigger_percent_str}")
        return

    if sl_trigger_percent <= 0:
        messagebox.showerror("Error", "SL trigger % must be > 0.")
        return

    # parse limit %
    try:
        sl_limit_percent = Decimal(sl_limit_percent_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid SL limit %: {sl_limit_percent_str}")
        return

    if sl_limit_percent <= 0:
        messagebox.showerror("Error", "SL limit % must be > 0.")
        return

    # optional: ensure limit deeper than trigger
    if sl_limit_percent < sl_trigger_percent:
        if not messagebox.askyesno(
            "Warning",
            "SL limit % is smaller than SL trigger %.\n"
            "Usually the limit should be >= trigger (deeper).\n\nContinue anyway?"
        ):
            return

    sl_trigger_factor = sl_trigger_percent / Decimal("100")
    sl_limit_factor = sl_limit_percent / Decimal("100")

    # Base asset & free balance
    try:
        info = get_symbol_info_cached(symbol)
    except Exception as e:
        log(f"[ERROR] Symbol info: {e}")
        messagebox.showerror("Error", str(e))
        return

    base_asset = info.get("baseAsset")
    if not base_asset:
        messagebox.showerror("Error", f"baseAsset not found for {symbol}.")
        return

    try:
        balance = client.get_asset_balance(asset=base_asset)
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_asset_balance({base_asset}): {e}")
        messagebox.showerror("API Error", str(e))
        return

    free_str = balance.get("free", "0")
    try:
        free_amount = Decimal(free_str)
    except Exception:
        messagebox.showerror("Error", f"Invalid balance: {free_str}")
        return

    if free_amount <= 0:
        log(f"[INFO] No free {base_asset} to protect with SL.")
        messagebox.showinfo("Info", f"No free {base_asset} balance to set SL for.")
        return

    tick_size, step_size, min_notional = get_filters(symbol)
    qty_rounded = round_down_step(free_amount, step_size)
    if qty_rounded <= 0:
        messagebox.showerror("Error", "Rounded quantity is 0.")
        return

    # current price as basis
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        current_price = Decimal(ticker["price"])
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] get_symbol_ticker({symbol}): {e}")
        messagebox.showerror("API Error", str(e))
        return

    if current_price <= 0:
        messagebox.showerror("Error", f"Invalid price for {symbol}: {current_price}")
        return

    avg_price = current_price  # Basis für SL-Prozent

    raw_stop = avg_price * (Decimal("1") - sl_trigger_factor)
    raw_limit = avg_price * (Decimal("1") - sl_limit_factor)

    raw_stop = round_down_step(raw_stop, tick_size)
    raw_limit = round_down_step(raw_limit, tick_size)

    sl_stop_price = max(raw_stop, raw_limit)
    sl_limit_price = min(raw_stop, raw_limit)

    log(f"[INFO] Add SL for free {base_asset}:")
    log(f"       Qty       : {fmt_decimal(qty_rounded)}")
    log(f"       BasisPrice: {fmt_decimal(avg_price)}")
    log(f"       Trigger   : {fmt_decimal(sl_stop_price)}")
    log(f"       Limit     : {fmt_decimal(sl_limit_price)}")

    try:
        sl_order = client.create_order(
            symbol=symbol,
            side="SELL",
            type="STOP_LOSS_LIMIT",
            timeInForce="GTC",
            quantity=float(qty_rounded),
            price=str(sl_limit_price),
            stopPrice=str(sl_stop_price),
            newOrderRespType="FULL"
        )
        log(f"[OK] Added SL for free coins. OrderId={sl_order.get('orderId')} Status={sl_order.get('status')}")
    except (BinanceAPIException, BinanceRequestException) as e:
        log(f"[ERROR] Add-SL failed: {e}")
        messagebox.showerror("API Error", str(e))

# =========================
# GUI CALLBACKS
# =========================
def on_calc_from_percent(event=None, show_error: bool = True):
    symbol = combo_symbol.get().strip().upper()
    pct_str = entry_pct.get().strip()
    if not symbol:
        if show_error:
            messagebox.showerror("Error", "Select a symbol.")
        return
    if not pct_str:
        if show_error:
            messagebox.showerror("Error", "Enter percentage.")
        return

    if not symbol.endswith("USDT"):
        if show_error:
            messagebox.showerror("Error", "Percent-buy is implemented only for USDT pairs.")
        return

    try:
        pct = Decimal(pct_str)
    except Exception:
        if show_error:
            messagebox.showerror("Error", f"Invalid percentage: {pct_str}")
        return

    if pct <= 0 or pct > 100:
        if show_error:
            messagebox.showerror("Error", "Percent must be between 0 and 100.")
        return

    usdt_balance = get_usdt_balance()
    if usdt_balance <= 0:
        if show_error:
            messagebox.showerror("Error", "USDT balance is 0.")
        return

    usdt_to_spend = usdt_balance * pct / Decimal("100")

    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = Decimal(ticker["price"])
    except (BinanceAPIException, BinanceRequestException) as e:
        if show_error:
            log(f"[ERROR] get_symbol_ticker({symbol}): {e}")
            messagebox.showerror("API Error", str(e))
        return

    if price <= 0:
        if show_error:
            messagebox.showerror("Error", f"Invalid price for {symbol}: {price}")
        return

    base_amount = usdt_to_spend / price
    tick_size, step_size, min_notional = get_filters(symbol)
    base_amount_rounded = round_down_step(base_amount, step_size)
    rounded_str = fmt_decimal(base_amount_rounded)

    info = get_symbol_info_cached(symbol)
    base_asset = info.get("baseAsset", "BASE")

    label_pct_info.configure(
        text=f"~ {usdt_to_spend:.2f} USDT"
    )
    if show_error:
        log(f"[INFO] % buy: {pct}% USDT -> {usdt_to_spend:.2f} USDT -> {fmt_decimal(base_amount_rounded)} {base_asset}")
    return rounded_str
def on_buy_spot():
    # immer zuerst kalkulieren
    qty = on_calc_from_percent()
    symbol = combo_symbol.get().strip().upper()
    if not symbol or not qty:
        messagebox.showerror("Error", "Symbol and quantity required.")
        return
    buy_spot(symbol, qty)
def on_buy_spot_sl():
    # auch hier immer zuerst Calc ausführen
    qty = on_calc_from_percent()
    symbol = combo_symbol.get().strip().upper()
    sl_trig = entry_sl_trigger.get().strip()
    sl_lim = entry_sl_limit.get().strip()

    if not symbol or not qty or not sl_trig or not sl_lim:
        messagebox.showerror("Error", "Symbol, quantity, SL trigger % and SL limit % required.")
        return
    buy_spot_with_sl(symbol, qty, sl_trig, sl_lim)
def on_sell_all():
    symbol = combo_symbol.get().strip().upper()
    if not symbol:
        messagebox.showerror("Error", "Symbol required.")
        return
    sell_all(symbol)
def on_add_sl_for_free():
    symbol = combo_symbol.get().strip().upper()
    sl_trig = entry_sl_trigger.get().strip()
    sl_lim = entry_sl_limit.get().strip()

    if not symbol or not sl_trig or not sl_lim:
        messagebox.showerror("Error", "Symbol, SL trigger % and SL limit % required.")
        return
    add_sl_for_free(symbol, sl_trig, sl_lim)
def on_clear_all_sl():
    symbol = combo_symbol.get().strip().upper()
    if not symbol:
        messagebox.showerror("Error", "Select a symbol.")
        return
    cancel_sl_orders(symbol)
def on_refresh_balance():
    refresh_account_labels()
def on_sl_trigger_change(event=None):
    text = entry_sl_trigger.get().strip()
    if not text:
        return
    try:
        trig = Decimal(text)
    except Exception:
        return

    new_limit = trig + Decimal("0.1")
    entry_sl_limit.delete(0, "end")
    entry_sl_limit.insert(0, str(new_limit))
def on_symbol_type(event=None):
    """
    Filtere das Dropdown erst ab 3 Zeichen und lasse es leer darunter.
    """
    text = combo_symbol.get().strip().upper()
    # choose filter list
    options = ALL_USDT if len(text) < 3 else [s for s in ALL_USDT if text in s]
    if not text:
        options = ALL_USDT
    combo_symbol.configure(values=options)

# =========================
# region START: CLIENT & GUI (customtkinter)
# =========================
client = create_client()

# dynamisch: alle USDT Paare
ALL_USDT = get_all_usdt_symbols()

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.title("Binance Auto SL/TP")
x=300
y=500
root.geometry(f"{x}x{y}")
root.wm_attributes("-topmost", True)
base_font = ("Segoe UI", 14)
mono_font = ("Consolas", 13)

root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(0, weight=1)

main_frame = ctk.CTkFrame(root, corner_radius=10)
main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
# layout for 5 columns now (all even)
for col in range(5):
    main_frame.grid_columnconfigure(col, weight=1)
main_frame.grid_rowconfigure(7, weight=1)

# Account info
info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
info_frame.grid(row=0, column=0, columnspan=5, sticky="ew", padx=2, pady=2)
info_frame.grid_columnconfigure(1, weight=1)

label_usdt = ctk.CTkLabel(info_frame, text="free: -", font=base_font, anchor="w")
label_usdt.grid(row=0, column=0, sticky="w", padx=2, pady=2)

label_total = ctk.CTkLabel(info_frame, text="total: - USDT", font=base_font, anchor="w")
label_total.grid(row=0, column=1, sticky="w", padx=2, pady=2)

# Symbol dropdown + Quantity in one row (1/2/1/1)
label_symbol = ctk.CTkLabel(main_frame, text="Coin:", font=base_font, anchor="w")
label_symbol.grid(row=1, column=0, sticky="ew", padx=2, pady=2)

combo_symbol = ctk.CTkComboBox(
    main_frame,
    values=ALL_USDT,
    font=base_font,
    dropdown_font=base_font,
)
combo_symbol.set("BNBUSDT")
combo_symbol.grid(row=1, column=1, columnspan=2, sticky="ew", padx=2, pady=2)
combo_symbol.bind("<KeyRelease>", on_symbol_type)

label_price = ctk.CTkLabel(main_frame, text="Price:", font=base_font, anchor="w")
label_price.grid(row=1, column=3, sticky="ew", padx=2, pady=2)

label_price_value = ctk.CTkLabel(main_frame, text="-", font=base_font, anchor="w")
label_price_value.grid(row=1, column=4, sticky="ew", padx=2, pady=2)

# SL Trigger / Limit % (3/1/1)
label_sl = ctk.CTkLabel(main_frame, text="SL Trig/Lim %", font=base_font, anchor="w")
label_sl.grid(row=3, column=0, columnspan=3, sticky="ew", padx=2, pady=2)

entry_sl_trigger = ctk.CTkEntry(main_frame, font=base_font)
entry_sl_trigger.insert(0, "0.5")
entry_sl_trigger.grid(row=3, column=3, sticky="ew", padx=2, pady=2)

entry_sl_limit = ctk.CTkEntry(main_frame, font=base_font)
entry_sl_limit.insert(0, "0.6")
entry_sl_limit.grid(row=3, column=4, sticky="ew", padx=2, pady=2)

entry_sl_trigger.bind("<KeyRelease>", on_sl_trigger_change)
entry_sl_trigger.bind("<FocusOut>", on_sl_trigger_change)

# % of USDT balance (1/1/3)
label_pct = ctk.CTkLabel(main_frame, text="% USDT:", font=base_font, anchor="w")
label_pct.grid(row=4, column=0, sticky="ew", padx=2, pady=2)

entry_pct = ctk.CTkEntry(main_frame, font=base_font)
entry_pct.insert(0, "10")
entry_pct.grid(row=4, column=1, sticky="ew", padx=2, pady=2)
entry_pct.bind("<KeyRelease>", lambda e: on_calc_from_percent(show_error=False))
entry_pct.bind("<FocusOut>", lambda e: on_calc_from_percent(show_error=False))

label_pct_info = ctk.CTkLabel(main_frame, text="", font=("Segoe UI", 12), anchor="w")
label_pct_info.grid(row=4, column=2, columnspan=3, sticky="ew", padx=2, pady=2)

# Buttons (1/1/1/1/1)
btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
btn_frame.grid(row=5, column=0, columnspan=5, padx=2, pady=2, sticky="ew")
for col in range(5):
    btn_frame.grid_columnconfigure(col, weight=1)

btn_buy = ctk.CTkButton(btn_frame, text="+", command=on_buy_spot, font=base_font)
btn_buy.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

btn_buy_sl = ctk.CTkButton(btn_frame, text="+SL", command=on_buy_spot_sl, font=base_font)
btn_buy_sl.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

btn_sell_all = ctk.CTkButton(btn_frame, text="-*", command=on_sell_all, font=base_font)
btn_sell_all.grid(row=0, column=2, padx=2, pady=2, sticky="ew")

btn_add_sl = ctk.CTkButton(btn_frame, text="SL*", command=on_add_sl_for_free, font=base_font)
btn_add_sl.grid(row=0, column=3, padx=2, pady=2, sticky="ew")

btn_clear_sl = ctk.CTkButton(btn_frame, text="!SL*", command=on_clear_all_sl, font=base_font)
btn_clear_sl.grid(row=0, column=4, padx=2, pady=2, sticky="ew")

# Log
label_log = ctk.CTkLabel(main_frame, text="Log:", font=base_font, anchor="w")
label_log.grid(row=6, column=0, columnspan=5, sticky="w", padx=2, pady=2)

log_text = ctk.CTkTextbox(
    main_frame,
    height=260,
    font=mono_font
)
log_text.grid(row=7, column=0, columnspan=5, sticky="nsew", padx=2, pady=2)
log_text.configure(state="disabled")

# endregion
# =========================

# Dynamische Breiten basierend auf Fensterbreite
resize_after_id = None
def resize_widgets():
    try:
        total = max(main_frame.winfo_width(), 200)
        padding = 6 * 5  # rough padding per row
        col = max(60, (total - padding) / 5)
        label_symbol.configure(width=int(col))
        combo_symbol.configure(width=int(col * 2))
        label_price.configure(width=int(col))
        label_price_value.configure(width=int(col))
        label_sl.configure(width=int(col * 3))
        entry_sl_trigger.configure(width=int(col))
        entry_sl_limit.configure(width=int(col))
        label_pct.configure(width=int(col))
        entry_pct.configure(width=int(col))
        label_pct_info.configure(width=int(col * 3))
        for btn in (btn_buy, btn_buy_sl, btn_sell_all, btn_add_sl, btn_clear_sl):
            btn.configure(width=int(col))
    except Exception:
        pass

def schedule_resize(event=None):
    global resize_after_id
    if resize_after_id is not None:
        try:
            root.after_cancel(resize_after_id)
        except Exception:
            pass
    resize_after_id = root.after(120, resize_widgets)

root.bind("<Configure>", schedule_resize)
schedule_resize()
log("[INFO] Binance Auto SL/TP started.")
on_calc_from_percent()
# =========================
# AUTO REFRESH
# =========================
def auto_refresh():
    try:
        refresh_account_labels()
    finally:
        root.after(5000, auto_refresh)
auto_refresh()

def refresh_symbol_value():
    symbol = combo_symbol.get().strip().upper()
    if not symbol:
        label_price_value.configure(text="-")
        root.after(1000, refresh_symbol_value)
        return
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = Decimal(ticker["price"])
        price_str = format(price, ".5g")  # show 5 significant digits
        label_price_value.configure(text=price_str)
    except (BinanceAPIException, BinanceRequestException):
        label_price_value.configure(text="n/a")
    except Exception:
        label_price_value.configure(text="n/a")
    root.after(1000, refresh_symbol_value)
refresh_symbol_value()

# =========================
# region TOOLTIPS
# =========================
add_tooltip(label_usdt, "Free USDT balance on your spot account.")
add_tooltip(label_total, "Approximate total value of your spot account in USDT.")
add_tooltip(label_price_value, "Live price of the selected symbol in USDT (updates every second).")

add_tooltip(label_symbol, "Trading pair, e.g. BNBUSDT (base / quote).")
add_tooltip(combo_symbol, "Pick a USDT pair. This selection drives all actions (+, +SL, -*, SL*, !SL*).")

add_tooltip(label_sl, "Stop-loss percentages: Trigger becomes stopPrice, Limit becomes price (usually a bit lower).")
add_tooltip(entry_sl_trigger, "SL trigger % below entry/current price where stopPrice should fire (e.g. 1 = -1%).")
add_tooltip(entry_sl_limit, "SL limit % sets the limit price; typically slightly deeper than the trigger (e.g. 1.2%).")

add_tooltip(label_pct, "Percent of your free USDT balance you want to allocate to this symbol.")
add_tooltip(entry_pct, "Enter % of free USDT to spend (e.g. 10 = 10% of your free USDT).")
add_tooltip(label_pct_info, "Shows the converted USDT amount and resulting base-asset quantity.")

add_tooltip(btn_buy, "+ : Market buy without SL. Recalculates qty from % and buys that amount.")
add_tooltip(btn_buy_sl, "+SL : Market buy then place SL. Uses % calc + qty + SL Trigger/Limit % in one flow.")
add_tooltip(btn_sell_all, "-* : Market sell the entire FREE balance of this base asset. Existing SL/TP orders for this symbol are canceled first.")
add_tooltip(btn_add_sl, "SL* : Set/refresh a stop-loss for all FREE coins of this symbol without buying. Uses current SL Trigger/Limit % fields.")
add_tooltip(btn_clear_sl, "!SL* : Cancel all SL/TP orders for the currently selected symbol only.")

# endregion

root.mainloop()
