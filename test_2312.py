from FinMind_Stock import get_finmind_indicators

def to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

r = get_finmind_indicators('2312')
if not isinstance(r, dict):
    print(r)
    raise SystemExit(0)

print(f"股票: {r.get('股票代號')}    日期: {r.get('日期')}")
keys = ['今日股價','BBand 中軌 (20MA)','BBand 寬度 (%)','RSI (6)','K值 (9)','D值 (3)','ADX','+DI','-DI','今日成交量 (張)','5 日均量 (張)']
for k in keys:
    print(f"{k}: {r.get(k)}")

price = to_float(r.get('今日股價'))
mid = to_float(r.get('BBand 中軌 (20MA)'))
width = to_float(r.get('BBand 寬度 (%)'))
rsi6 = to_float(r.get('RSI (6)'))
k_val = to_float(r.get('K值 (9)'))
d_val = to_float(r.get('D值 (3)'))
adx = to_float(r.get('ADX'))
di_p = to_float(r.get('+DI'))
di_m = to_float(r.get('-DI'))
vol = to_float(r.get('今日成交量 (張)'))
vol_ma5 = to_float(r.get('5 日均量 (張)'))

checks = []

c1 = price > mid
checks.append(("價在中軌上", "✔" if c1 else "✘", 1 if c1 else 0))

if width < 6:
    c2_sym = "✔✔"
    c2_cnt = 2
elif 6 <= width < 20:
    c2_sym = "✔"
    c2_cnt = 1
else:
    c2_sym = "✘"
    c2_cnt = 0
checks.append(("BBand 寬度", c2_sym, c2_cnt))

c3 = (rsi6 >= 50 and rsi6 <= 70)
checks.append(("RSI 50–70", "✔" if c3 else "✘", 1 if c3 else 0))

c4 = (k_val > d_val)
checks.append(("KD 黃金交叉", "✔" if c4 else "✘", 1 if c4 else 0))

c5 = (vol >= vol_ma5)
checks.append(("量 ≥ 5 日量", "✔" if c5 else "✘", 1 if c5 else 0))

c6 = (adx > 20 and adx < 30)
checks.append(("ADX 安全區", "✔" if c6 else "✘", 1 if c6 else 0))

c7 = (di_p > di_m)
checks.append(("+DI > -DI", "✔" if c7 else "✘", 1 if c7 else 0))

print("\n判斷結果:")
for it in checks:
    print(f"{it[0]:15}: {it[1]}")

total = sum(it[2] for it in checks)
print(f"\n總分: {total}")
print("買賣訊號: ", "BUY" if total >= 6 else "No")
