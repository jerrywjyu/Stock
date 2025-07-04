
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import ta
import matplotlib

# 設定中文字型（以 Windows 常見字型為例，若無可改用 SimHei 或其他）
matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

symbol = "9945.TW"
df = yf.download(symbol, start="2024-01-01", end="2025-07-02", auto_adjust=False)

# 扁平化欄位名稱
df.columns = [col[0] for col in df.columns]

print(df.columns)
print(df.head())

df = df.dropna(subset=['High', 'Low', 'Close']).reset_index(drop=True)
df['MA5'] = df['Close'].rolling(window=5).mean()
df['MA20'] = df['Close'].rolling(window=20).mean()
df['MA60'] = df['Close'].rolling(window=60).mean()

print(df[['High', 'Low', 'Close']].head())
print(df[['High', 'Low', 'Close']].shape)
print("High shape:", df['High'].values.shape)
print("Low shape:", df['Low'].values.shape)
print("Close shape:", df['Close'].values.shape)
print("DataFrame shape:", df.shape)


# 計算 KD 指標 (Stochastic Oscillator)
stoch = ta.momentum.StochasticOscillator(
    high=df['High'],
    low=df['Low'],
    close=df['Close'],
    window=14,
    smooth_window=3
)
df['slowk'] = stoch.stoch()
df['slowd'] = stoch.stoch_signal()

# 計算 RSI
df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()

# 畫圖：股價與均線
plt.figure(figsize=(14, 6))
plt.plot(df['Close'], label='收盤價', color='black')
plt.plot(df['MA5'], label='5日均線', linestyle='--', color='blue')
plt.plot(df['MA20'], label='20日均線', linestyle='--', color='green')
plt.plot(df['MA60'], label='60日均線', linestyle='--', color='red')
plt.title(f"{symbol} 股價與均線")
plt.xlabel("日期")
plt.ylabel("價格 (TWD)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# 畫圖：KD 指標
plt.figure(figsize=(14, 4))
plt.plot(df['slowk'], label='%K', color='orange')
plt.plot(df['slowd'], label='%D', color='purple')
plt.axhline(80, color='gray', linestyle='--')
plt.axhline(20, color='gray', linestyle='--')
plt.title("KD 指標")
plt.legend()
plt.tight_layout()
plt.show()

# 畫圖：RSI 指標
plt.figure(figsize=(14, 4))
plt.plot(df['RSI'], label='RSI', color='teal')
plt.axhline(70, color='red', linestyle='--', label='超買')
plt.axhline(30, color='green', linestyle='--', label='超賣')
plt.title("RSI 指標")
plt.legend()
plt.tight_layout()
plt.show()
