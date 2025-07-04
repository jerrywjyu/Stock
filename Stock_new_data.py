import requests
import pandas as pd
import matplotlib.pyplot as plt
import ta
from datetime import datetime, timedelta

import matplotlib

# 設定中文字型（以 Windows 常見字型為例，若無可改用 SimHei 或其他）
matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# ----------- 參數設定 -----------
stock_id = "2497"   # 怡利電代碼
days = 10            # 抓過去幾天
# ------------------------------

def fetch_twse_daily(date_str):
    url = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
    params = {
        "response": "json",
        "date": date_str,
        "type": "ALLBUT0999"
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    res = requests.get(url, params=params, headers=headers)
    if res.status_code != 200:
        return None
    data = res.json()
    print(f"{date_str} API keys: {list(data.keys())}")
    for k in data.keys():
        if isinstance(data[k], list):
            print(f"{date_str} {k}: {len(data[k])} rows")

    # 嘗試自動尋找包含「證券代號」欄位的表格
    tables = data.get("tables", [])
    for idx, table in enumerate(tables):
        fields = table.get("fields", [])
        if "證券代號" in fields:
            print(f"{date_str} 使用 tables[{idx}]，欄位: {fields}")
            rows = table.get("data", [])
            df = pd.DataFrame(rows, columns=fields)
            return df
    # 若找不到，回傳空 DataFrame
    print(f"{date_str} 找不到包含 '證券代號' 的表格")
    return pd.DataFrame()

# 建立歷史資料
records = []
today = datetime.today()
for i in range(days):
    date = today - timedelta(days=i)
    if date.weekday() >= 5:
        continue  # 跳過週末
    date_str = date.strftime("%Y%m%d")
    daily_df = fetch_twse_daily(date_str)
    if daily_df is None:
        continue

    if "證券代號" not in daily_df.columns:
        print(f"{date_str} 缺少 '證券代號' 欄位，實際欄位: {daily_df.columns.tolist()}")
        continue

    daily_df = daily_df[daily_df["證券代號"] == stock_id]
    if not daily_df.empty:
        try:
            row = daily_df.iloc[0]
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": float(row["收盤價"].replace(",", "").replace('--', '0')),
                "high": float(row["最高價"].replace(",", "").replace('--', '0')),
                "low": float(row["最低價"].replace(",", "").replace('--', '0')),
                "open": float(row["開盤價"].replace(",", "").replace('--', '0')),
            })
        except Exception as e:
            print(f"{date_str} 解析資料失敗: {e}")
            continue


# 建立 DataFrame
if not records:
    print("無有效資料可用，請檢查股票代碼、日期區間或 API 回傳內容。")
    exit()
df = pd.DataFrame(records)
df = df.sort_values("date")
df.set_index("date", inplace=True)

# 計算技術指標
df["MA5"] = df["close"].rolling(5).mean()
df["MA20"] = df["close"].rolling(20).mean()
df["MA60"] = df["close"].rolling(60).mean()
# KD 指標 (Stochastic Oscillator)
stoch = ta.momentum.StochasticOscillator(
    high=df["high"],
    low=df["low"],
    close=df["close"],
    window=14,
    smooth_window=3
)
df["slowk"] = stoch.stoch()
df["slowd"] = stoch.stoch_signal()

# RSI 指標
df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

# ------- 繪圖：均線 --------
plt.figure(figsize=(14, 6))
plt.plot(df["close"], label="收盤價", color="black")
plt.plot(df["MA5"], label="5日均線", linestyle='--', color="blue")
plt.plot(df["MA20"], label="20日均線", linestyle='--', color="green")
plt.plot(df["MA60"], label="60日均線", linestyle='--', color="red")
plt.title(f"{stock_id} 股價與均線")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# ------- 繪圖：KD --------
plt.figure(figsize=(14, 4))
plt.plot(df["slowk"], label="%K", color="orange")
plt.plot(df["slowd"], label="%D", color="purple")
plt.axhline(80, color='gray', linestyle='--')
plt.axhline(20, color='gray', linestyle='--')
plt.title("KD 指標")
plt.legend()
plt.tight_layout()
plt.show()

# ------- 繪圖：RSI --------
plt.figure(figsize=(14, 4))
plt.plot(df["RSI"], label="RSI", color="teal")
plt.axhline(70, color='red', linestyle='--', label='超買')
plt.axhline(30, color='green', linestyle='--', label='超賣')
plt.title("RSI 指標")
plt.legend()
plt.tight_layout()
plt.show()
