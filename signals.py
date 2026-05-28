import requests
import time
from datetime import datetime

# ══════════════════════════════════════════
#  APNA TOKEN AUR CHAT ID YAHAN DAALO
# ══════════════════════════════════════════
TELEGRAM_TOKEN   = "8840920612:AAHNcg-7NyE44LxjRw0ytfX-toz0ymbXsPg"
TELEGRAM_CHAT_ID  = "5911994666"

# ══════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════
MAX_PRICE  = 1.0
MIN_VOLUME = 1000000
TOP_COINS  = 20

def send_telegram(message):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, data=data, timeout=10)
        print(f"Telegram response: {resp.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_coins():
    try:
        url    = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "percent_change_24h_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": False
        }
        response = requests.get(url, params=params, timeout=20)
        data     = response.json()
        if not isinstance(data, list):
            print(f"CoinGecko error: {data}")
            return []
        filtered = []
        for coin in data:
            try:
                price  = float(coin.get('current_price') or 0)
                volume = float(coin.get('total_volume') or 0)
                change = float(coin.get('price_change_percentage_24h') or 0)
                cid    = coin.get('id', '')
                symbol = coin.get('symbol', '').upper()
                name   = coin.get('name', '')
            except:
                continue
            if price <= 0 or price >= MAX_PRICE:
                continue
            if volume < MIN_VOLUME:
                continue
            filtered.append({
                'id': cid, 'symbol': symbol, 'name': name,
                'price': price, 'change': change, 'volume': volume
            })
        filtered.sort(key=lambda x: x['change'], reverse=True)
        print(f"✅ {len(filtered)} coins mile")
        return filtered[:40]
    except Exception as e:
        print(f"Coins fetch error: {e}")
        return []

def calc_ema(prices, period):
    if not prices or len(prices) < period:
        return None
    k   = 2 / (period + 1)
    ema = float(prices[0])
    for price in prices[1:]:
        ema = float(price) * k + ema * (1 - k)
    return ema

def get_candles_4h(coin_id):
    try:
        url      = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params   = {"vs_currency": "usd", "days": "90"}
        response = requests.get(url, params=params, timeout=15)
        data     = response.json()
        if not isinstance(data, list) or len(data) < 50:
            return None, None, None
        closes = [float(c[4]) for c in data]
        highs  = [float(c[2]) for c in data]
        lows   = [float(c[3]) for c in data]
        return closes, highs, lows
    except:
        return None, None, None

def get_candles_1h(coin_id):
    try:
        url      = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params   = {"vs_currency": "usd", "days": "7"}
        response = requests.get(url, params=params, timeout=15)
        data     = response.json()
        if not isinstance(data, list) or len(data) < 30:
            return None, None, None
        closes = [float(c[4]) for c in data]
        highs  = [float(c[2]) for c in data]
        lows   = [float(c[3]) for c in data]
        return closes, highs, lows
    except:
        return None, None, None

def check_signal(coin):
    cid   = coin['id']
    price = coin['price']
    closes_4h, highs_4h, lows_4h = get_candles_4h(cid)
    time.sleep(1.5)
    if not closes_4h or len(closes_4h) < 50:
        return None
    ema200 = calc_ema(closes_4h, min(200, len(closes_4h)))
    if not ema200:
        return None
    trend = 'LONG' if price > ema200 else 'SHORT'
    closes_1h, highs_1h, lows_1h = get_candles_1h(cid)
    time.sleep(1.5)
    if not closes_1h or len(closes_1h) < 25:
        return None
    ema20_now  = calc_ema(closes_1h,      min(20, len(closes_1h)))
    ema50_now  = calc_ema(closes_1h,      min(50, len(closes_1h)))
    ema20_prev = calc_ema(closes_1h[:-1], min(20, len(closes_1h)-1))
    ema50_prev = calc_ema(closes_1h[:-1], min(50, len(closes_1h)-1))
    if not all([ema20_now, ema50_now, ema20_prev, ema50_prev]):
        return None
    bullish_cross = (ema20_prev < ema50_prev) and (ema20_now > ema50_now)
    bearish_cross = (ema20_prev > ema50_prev) and (ema20_now < ema50_now)
    if trend == 'LONG' and bullish_cross:
        action = 'BUY LONG'
    elif trend == 'SHORT' and bearish_cross:
        action = 'SELL SHORT'
    else:
        return None
    atr = 0
    if highs_4h and lows_4h:
        recent = list(zip(highs_4h[-14:], lows_4h[-14:]))
        atr    = sum(h - l for h, l in recent) / len(recent)
    if atr == 0:
        atr = price * 0.03
    if action == 'BUY LONG':
        tp1 = price + atr * 1.5
        tp2 = price + atr * 2.8
        sl  = price - atr * 0.8
    else:
        tp1 = price - atr * 1.5
        tp2 = price - atr * 2.8
        sl  = price + atr * 0.8
    risk   = abs(price - sl)
    reward = abs(tp1 - price)
    rr     = round(reward / risk, 1) if risk > 0 else 0
    return {
        'name': coin['name'], 'symbol': coin['symbol'],
        'price': price, 'change': coin['change'], 'volume': coin['volume'],
        'action': action, 'tp1': tp1, 'tp2': tp2, 'sl': sl, 'rr': rr,
        'ema200': ema200, 'ema20': ema20_now, 'ema50': ema50_now,
    }

def fp(p):
    if p <= 0:       return "$0"
    if p < 0.000001: return f"${p:.10f}"
    if p < 0.0001:   return f"${p:.8f}"
    if p < 0.01:     return f"${p:.6f}"
    return           f"${p:.4f}"

def fv(v):
    if v >= 1_000_000_000: return f"${v/1_000_000_000:.1f}B"
    if v >= 1_000_000:     return f"${v/1_000_000:.1f}M"
    return                 f"${v/1_000:.0f}K"

def format_message(rank, s):
    icon  = "🟢" if s['action'] == 'BUY LONG' else "🔴"
    trend = "📈 BULLISH" if s['action'] == 'BUY LONG' else "📉 BEARISH"
    sign  = "+" if s['change'] >= 0 else ""
    return (
        f"{icon} <b>#{rank} {s['name']} ({s['symbol']}/USDT)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Action     : <b>{s['action']}</b>\n"
        f"💪 Confidence : <b>HIGH 🔥🔥</b>\n"
        f"📊 Trend      : {trend}\n"
        f"🔔 Trigger    : <b>FRESH EMA CROSS ✅</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Entry  : <code>{fp(s['price'])}</code>\n"
        f"📈 24h    : <code>{sign}{s['change']:.2f}%</code>\n"
        f"💧 Volume : <code>{fv(s['volume'])}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 TP1    : <code>{fp(s['tp1'])}</code>\n"
        f"🎯 TP2    : <code>{fp(s['tp2'])}</code>\n"
        f"🛑 SL     : <code>{fp(s['sl'])}</code>\n"
        f"⚖️ R:R    : <code>1 : {s['rr']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📉 EMA200 (4H) : <code>{fp(s['ema200'])}</code>\n"
        f"📉 EMA20  (1H) : <code>{fp(s['ema20'])}</code>\n"
        f"📉 EMA50  (1H) : <code>{fp(s['ema50'])}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

def run_scan():
    now = datetime.now().strftime("%d %b %Y  %H:%M")
    print(f"\n{'='*40}")
    print(f"🔍 SCAN SHURU: {now}")
    print(f"{'='*40}")
    coins = get_coins()
    if not coins:
        send_telegram(f"❌ <b>Coins fetch error</b>\n🕐 {now}")
        return
    signals = []
    for i, coin in enumerate(coins):
        print(f"  Checking {coin['name']}... ({i+1}/{len(coins)})")
        result = check_signal(coin)
        if result:
            signals.append(result)
            print(f"  🔥 HIGH SIGNAL: {result['name']} — {result['action']}")
        if len(signals) >= TOP_COINS:
            break
    if not signals:
        send_telegram(
            f"🔍 <b>SCAN COMPLETE</b>\n"
            f"🕐 {now}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Koi HIGH signal nahi mila\n"
            f"⏰ Agla scan 30 min mein..."
        )
        return
    header = (
        f"⚡ <b>HIGH CONFIDENCE SIGNALS</b>\n"
        f"🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Price   : Under $1\n"
        f"✅ Volume  : $1M+\n"
        f"✅ Trend   : 4H EMA200\n"
        f"✅ Trigger : FRESH 1H EMA20×50\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 BUY  : {sum(1 for s in signals if s['action']=='BUY LONG')}\n"
        f"🔴 SELL : {sum(1 for s in signals if s['action']=='SELL SHORT')}\n"
        f"🔥 Total: {len(signals)} HIGH signals"
    )
    send_telegram(header)
    time.sleep(1)
    for i, s in enumerate(signals, 1):
        send_telegram(format_message(i, s))
        print(f"  📤 Sent: {s['name']}")
        time.sleep(0.5)
    send_telegram("⚠️ <i>Yeh financial advice nahi hai. Apna research zaroor karo.</i>")
    print(f"✅ {len(signals)} signals bhej diye!")

print("🤖 Signal Bot Shuru Ho Gaya!")
print("🔥 Sirf HIGH Confidence Signals")
print("📡 Data: CoinGecko API")
print("⏰ Har 30 minute mein scan hoga")
print("=" * 40)

while True:
    try:
        run_scan()
        print(f"\n⏰ 30 minute baad agla scan...")
        time.sleep(1800)
    except KeyboardInterrupt:
        print("\n👋 Bot band ho gaya!")
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(300)
