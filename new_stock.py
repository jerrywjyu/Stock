import ta
import pandas as pd
import numpy as np
import yfinance as yf
from twse_stock_list import fetch_twse_stock_list
from datetime import datetime, timedelta

def get_stock_name(symbol):
    """
    根據股票代號取得中文名稱
    :param symbol: 股票代號 (例如: '2497')
    :return: 中文名稱或代號本身
    """
    try:
        df = fetch_twse_stock_list()
        match = df[df['證券代號'] == symbol]
        if not match.empty:
            return match.iloc[0]['證券名稱']
    except Exception:
        pass
    return symbol

def get_taiwan_stock_indicators(symbol):
    """
    抓取台股技術指標
    :param symbol: 股票代號 (例如: '2497' 或 '8069')
    """
    try:
        # 1. 下載歷史資料 (使用 yfinance 下載最近 60 天資料)
        symbol_to_fetch = symbol if ('.' in symbol) else f"{symbol}.TW"
        df = yf.download(symbol_to_fetch, period="60d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return "找不到該股票資料，請檢查代號是否正確"

        # 若 yfinance 回傳 MultiIndex 欄位，扁平化
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        # 將索引日期轉為欄位
        df = df.reset_index()
        if 'Date' in df.columns:
            df = df.rename(columns={'Date': 'date'})
            try:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            except Exception:
                pass

        # 確保必要欄位存在：Open/High/Low/Close/Volume
        # 若欄位名稱不同，嘗試標準化
        col_map = {}
        if 'Open' in df.columns:
            col_map['Open'] = 'Open'
        if 'High' in df.columns:
            col_map['High'] = 'High'
        if 'Low' in df.columns:
            col_map['Low'] = 'Low'
        if 'Close' in df.columns:
            col_map['Close'] = 'Close'
        if 'Volume' in df.columns:
            col_map['Volume'] = 'Volume'
        if col_map:
            df = df.rename(columns={v: k for k, v in col_map.items()})

        # 2. 計算技術指標
        # 布林通道 (BBands: 20日, 2倍標準差)
        bb = ta.volatility.BollingerBands(pd.Series(df['Close'].values), n=20, ndev=2)
        df['BBU_20_2.0'] = bb.bollinger_hband()
        df['BBM_20_2.0'] = bb.bollinger_mavg()
        df['BBL_20_2.0'] = bb.bollinger_lband()
        
        # RSI (14日)
        rsi_series = pd.Series(df['Close'].values)
        df['RSI_14'] = ta.momentum.RSIIndicator(rsi_series, n=14).rsi()
        
        # KD Stochastic (9, 3, 3)
        high_series = pd.Series(df['High'].values)
        low_series = pd.Series(df['Low'].values)
        close_series = pd.Series(df['Close'].values)
        stoch = ta.momentum.StochasticOscillator(
            high=high_series, low=low_series, close=close_series, 
            n=9, d_n=3
        )
        df['STOCHk_9_3_3'] = stoch.stoch()
        df['STOCHd_9_3_3'] = stoch.stoch_signal()
        
        # ADX / +DI / -DI (14日)
        adx = ta.trend.ADXIndicator(high_series, low_series, close_series, n=14)
        df['ADX_14'] = adx.adx()
        df['DMP_14'] = adx.adx_pos()
        df['DMN_14'] = adx.adx_neg()
        
        # 計算 BBand 寬度: (上限 - 下限) / 中線 * 100 (百分比)
        df['BB_Width'] = (df['BBU_20_2.0'] - df['BBL_20_2.0']) / df['BBM_20_2.0'] * 100
        # 計算 5日均量
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()

        # 4. 提取最新資訊
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 取得中文名稱
        stock_name = get_stock_name(symbol)

        def _to_thousands(x):
            try:
                if pd.isna(x):
                    return None
                return int(float(x) / 1000)
            except Exception:
                return None

        results = {
            "股票代號": symbol,
            "股票名稱": stock_name,
            "日期": str(latest['date']),
            "今日收盤": round(latest['Close'].item(), 2),
            "BBand 中軌": round(latest['BBM_20_2.0'].item(), 2),
            "BBand 上限": round(latest['BBU_20_2.0'].item(), 2),
            "BBand 下限": round(latest['BBL_20_2.0'].item(), 2),
            "BBand 寬度": round(latest['BB_Width'].item(), 2),
            "RSI (14)": round(latest['RSI_14'].item(), 2),
            "K值 (9)": round(latest['STOCHk_9_3_3'].item(), 2),
            "D值 (3)": round(latest['STOCHd_9_3_3'].item(), 2),
            "ADX": round(latest['ADX_14'].item(), 2),
            "+DI": round(latest['DMP_14'].item(), 2),
            "-DI": round(latest['DMN_14'].item(), 2),
            "昨日成交量": _to_thousands(prev['Volume'].item()),
            "今日成交量": _to_thousands(latest['Volume'].item()),
            "5日均量": _to_thousands(latest['Vol_MA5'].item())
        }
        return results

    except Exception as e:
        return f"發生錯誤: {e}"

# --- 測試執行 ---
# 怡利電 2497 (上市)
target_stock = "2497" 
data = get_taiwan_stock_indicators(target_stock)

if isinstance(data, dict):
    print(f"=== {data['股票代號']} {data['股票名稱']} 技術分析報告 ===")
    for key, value in data.items():
        if key not in ["股票代號", "股票名稱"]:
            print(f"{key}: {value}")
else:
    print(data)