import pandas as pd
import ta
from FinMind.data import DataLoader
from twse_stock_list import fetch_twse_stock_list

def search_stock(query):
    """
    根據股票代碼或名稱搜尋股票
    參數: query (字串) - 股票代碼或中文名稱
    回傳: 股票代碼 (字串)
    """
    df_stocks = fetch_twse_stock_list()     
    
    # 先嘗試精確匹配股票代碼
    if query in df_stocks['證券代號'].values:
        return query
    
    # 再嘗試模糊匹配股票名稱（使用 regex=False 避免特殊字符錯誤）
    matches = df_stocks[df_stocks['證券名稱'].str.contains(query, na=False, regex=False)]
    
    if len(matches) == 0:
        print(f"❌ 找不到包含 '{query}' 的股票")
        return None
    elif len(matches) == 1:
        stock_id = matches.iloc[0]['證券代號']
        stock_name = matches.iloc[0]['證券名稱']
        print(f"✓ 找到: {stock_id} - {stock_name}")
        return stock_id
    else:
        print(f"⚠️  找到多筆結果，請輸入更精確的名稱:")
        for idx, row in matches.iterrows():
            print(f"  {row['證券代號']} - {row['證券名稱']}")
        return None

def get_finmind_indicators(stock_id):
    """
    使用 FinMind 抓取台股數據並計算 BBand, RSI, KD, ADX, 成交量等指標
    """
    # 1. 初始化 FinMind 載入器
    dl = DataLoader()
    
    # 2. 抓取歷史資料 (建議抓取 100 天，確保長週期指標如 ADX 計算準確)
    # 起始日期設定在約三個月前
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime('%Y-%m-%d')
    
    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start_date
    )

    if df.empty:
        return "找不到該股票資料，請檢查代號是否正確。"

    # 3. 資料欄位標準化 - FinMind 欄位: date, open, max, min, close, Trading_Volume
    df.columns = df.columns.str.lower()  # 轉為小寫以標準化
    
    # 標準化欄位名稱
    column_mapping = {
        'open': 'Open',
        'max': 'High',        # FinMind 用 max 代替 high
        'min': 'Low',         # FinMind 用 min 代替 low
        'close': 'Close',
        'trading_volume': 'Volume'
    }
    
    for old_name, new_name in column_mapping.items():
        if old_name in df.columns:
            df[new_name] = df[old_name]
    
    # 將日期設為索引
    if 'date' in df.columns:
        df.index = pd.to_datetime(df['date'])
    
    # 4. 計算各項指數 (使用 ta 庫)
    # A. 布林通道 (20, 2)
    bb = ta.volatility.BollingerBands(df['Close'], n=20, ndev=2, fillna=False)
    df['BBM'] = bb.bollinger_mavg()
    df['BBU'] = bb.bollinger_hband()
    df['BBL'] = bb.bollinger_lband()
    
    # B. RSI (6日與14日)
    df['RSI_6'] = ta.momentum.RSIIndicator(df['Close'], n=6, fillna=False).rsi()
    df['RSI_14'] = ta.momentum.RSIIndicator(df['Close'], n=14, fillna=False).rsi()
    
    # C. KD Stochastic (9, 3, 3)
    kd = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'], n=9, d_n=3, fillna=False)
    df['K'] = kd.stoch()
    df['D'] = kd.stoch_signal()
    
    # --- 計算台股版 KD (9,3,3) - 校正後 ---
    df['MA5'] = ta.trend.sma_indicator(df['Close'], n=5)
    # 1. 計算 RSV
    df['9_high'] = df['High'].rolling(9).max()
    df['9_low'] = df['Low'].rolling(9).min()
    df['rsv'] = (df['Close'] - df['9_low']) / (df['9_high'] - df['9_low']) * 100
    df['rsv'] = df['rsv'].fillna(50)

    # 2. 遞迴計算 K, D
    k_values = [50]
    d_values = [50]
    rsv_list = df['rsv'].tolist()

    for i in range(1, len(rsv_list)):
        k_cur = (2/3) * k_values[-1] + (1/3) * rsv_list[i]
        d_cur = (2/3) * d_values[-1] + (1/3) * k_cur
        k_values.append(k_cur)
        d_values.append(d_cur)

    df['K_Corrected'] = k_values
    df['D_Corrected'] = d_values

    # D. ADX / +DI / -DI (14日)
    adx_obj = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'], n=14, fillna=False)
    df['ADX'] = adx_obj.adx()
    df['DI+'] = adx_obj.adx_pos()
    df['DI-'] = adx_obj.adx_neg()
    
    # E. 計算額外數值：BBand 寬度(%)、5日均量、成交張數
    df['BB_Width'] = ((df['BBU'] - df['BBL']) / df['BBM'] * 100)
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    df['Volume_Lots'] = df['Volume'] / 1000  # 轉為張數
    df['Vol_MA5_Lots'] = df['Vol_MA5'] / 1000

    # 5. 提取最新一日與前一日數據
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # 取得股票中文名稱
    df_stocks = fetch_twse_stock_list()
    stock_name_series = df_stocks[df_stocks['證券代號'] == stock_id]['證券名稱']
    stock_name = stock_name_series.iloc[0] if not stock_name_series.empty else stock_id

    def safe_int(val):
        """安全轉換為整數，處理 NaN"""
        if pd.isna(val):
            return 0
        return int(float(val))

    results = {
        "日期": latest['date'],
        "股票代號": stock_id,
        "股票名稱": stock_name,
        "今日股價": round(latest['Close'], 2),
        "MA5": round(latest['MA5'], 2) if not pd.isna(latest['MA5']) else 0,
        "BBand 中軌 (20MA)": round(latest['BBM'], 2),
        "BBand 上限": round(latest['BBU'], 2),
        "BBand 下限": round(latest['BBL'], 2),
        "BBand 寬度 (%)": round(latest['BB_Width'], 2),
        "RSI (6)": round(latest['RSI_6'], 2),
        "RSI (14)": round(latest['RSI_14'], 2),
        "K值(9, 3)-校正後": round(latest['K_Corrected'], 2),
        "D值(9, 3)-校正後": round(latest['D_Corrected'], 2),
        "ADX": round(latest['ADX'], 2),
        "+DI": round(latest['DI+'], 2),
        "-DI": round(latest['DI-'], 2),
        "前一日成交量 (張)": safe_int(prev['Volume_Lots']),
        "今日成交量 (張)": safe_int(latest['Volume_Lots']),
        "5 日均量 (張)": safe_int(latest['Vol_MA5_Lots'])
    }
    # --- 判斷項目: 計算 7 項條件與分數 ---
    def to_float(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    price = to_float(results.get('今日股價'))
    mid = to_float(results.get('BBand 中軌 (20MA)'))
    upper = to_float(results.get('BBand 上限'))
    lower = to_float(results.get('BBand 下限'))
    width = to_float(results.get('BBand 寬度 (%)'))
    rsi6 = to_float(results.get('RSI (6)'))
    k_val = to_float(results.get('K值(9, 3)-校正後'))
    d_val = to_float(results.get('D值(9, 3)-校正後'))
    adx = to_float(results.get('ADX'))
    di_p = to_float(results.get('+DI'))
    di_m = to_float(results.get('-DI'))
    vol = to_float(results.get('今日成交量 (張)'))
    prev_vol = to_float(results.get('前一日成交量 (張)'))
    vol_ma5 = to_float(results.get('5 日均量 (張)'))

    checks = []
    # ① 價在中軌上
    if price >= upper:
        checks.append({"項目": "價在中軌上", "狀態": "✔ (🔥 股價貼上軌)", "分數": 1})
    elif mid < price < upper:
        checks.append({"項目": "價在中軌上", "狀態": "✔ (✅ 中軌之上，正常趨勢)", "分數": 2})
    elif price <= lower:
        checks.append({"項目": "價在中軌上", "狀態": "✘ (❌ 股價貼下軌)", "分數": 0})
    else:
        checks.append({"項目": "價在中軌上", "狀態": "✘ (⚠️ 股價在中軌之下)", "分數": 0})

    # ② BBand 寬度（<6 -> ✔ 計1分；10<=x<20 -> ✔ 計2分）
    if width <= 6:
        checks.append({"項目": "BBand 寬度", "狀態": "✔ （🚨 極度壓縮)", "分數": 0})
    elif 6 < width <= 10:
        checks.append({"項目": "BBand 寬度", "狀態": "✔ (⚠️ 壓縮中)", "分數": 1})
    elif 10 < width <= 20:
        checks.append({"項目": "BBand 寬度", "狀態": "✔✔ (✅ 正常趨勢)", "分數": 2})
    elif 20 < width <= 30:
        checks.append({"項目": "BBand 寬度", "狀態": "✘ (⚠️ 趨勢擴張)", "分數": 0})
    else:
        checks.append({"項目": "BBand 寬度", "狀態": "✘ (❌ 極度過熱)", "分數": -1})

    # ③ RSI 50–70
    if rsi6 > 70:
        checks.append({"項目": "RSI 50–70", "狀態": "✘ (🚨 過熱)", "分數": 0})
    elif rsi6 < 50:
        checks.append({"項目": "RSI 50–70", "狀態": "✘ (⚠️ 弱勢)", "分數": 0})
    elif 60 < rsi6 <= 70:
        checks.append({"項目": "RSI 50–70", "狀態": "✔ (🔥 強勢區)", "分數": 1})
    else:
        checks.append({"項目": "RSI 50–70", "狀態": "✔ (✅ 最佳買點區)", "分數": 2})

    # ④ KD 黃金/死亡交叉
    if k_val > d_val:
        if 30 < k_val < 80:
            checks.append({"項目": "KD 黃金/死亡交叉", "狀態": "✔ (✅ 黃金交叉且多頭)", "分數": 2})
        elif k_val >= 80:
            checks.append({"項目": "KD 黃金/死亡交叉", "狀態": "✔ (⚠️ 黃金交叉但過熱)", "分數": 1})
    else:
        checks.append({"項目": "KD 黃金/死亡交叉", "狀態": "✘ (🚨 死亡交叉)", "分數": 0})
    # ⑤ 成交量
    # 1. 今日 > 5日均量*1.8 → ✔✔ (🚨 爆量) (2分)
    # 2. 今日 ≥ 5日均量*1.2 且 < 5日均量*1.8 → ✔ (有量) (1分)
    # 3. 0.8 × 5 日均量 ≤ 今日量 < 1.2 × 5 日均量 → ✔ (⚠️ 觀察) (0分)
    # 4. 今日 ≤ 5日均量*0.8 → ✘ (無量/量縮) (0分)
    if vol > vol_ma5 * 1.8:
        checks.append({"項目": "成交量", "狀態": "✔✔ (🚨 爆量)", "分數": 2})
    elif vol >= vol_ma5 * 1.2:
        checks.append({"項目": "成交量", "狀態": "✔ (✅ 有量)", "分數": 1})
    elif vol >= vol_ma5 * 0.8:
        checks.append({"項目": "成交量", "狀態": "✔ (⚠️ 觀察)", "分數": 0})
    else:
        checks.append({"項目": "成交量", "狀態": "✘ (❌ 無量/量縮)", "分數": 0})

    # ⑥ ADX 安全區
    if adx < 15:
        checks.append({"項目": "ADX 安全區", "狀態": "✘ (❌ 無趨勢/盤整)", "分數": -1})
    elif 15 <= adx < 20:
        checks.append({"項目": "ADX 安全區", "狀態": "✔ (⚠️ 多頭趨勢剛開始)", "分數": 0})
    elif 20 <= adx < 25:
        checks.append({"項目": "ADX 安全區", "狀態": "✔✔ (✅ 多頭趨勢，可買)", "分數": 2})
    elif 25 <= adx < 35:
        checks.append({"項目": "ADX 安全區", "狀態": "✔ (✅ 多頭趨勢強，續抱)", "分數": 1})
    else:
        checks.append({"項目": "ADX 安全區", "狀態": "✔ (🚨 多頭趨勢過熱)", "分數": 0})

    # ⑦ 趨勢方向 (+DI/-DI)
    # 若+DI > -DI 很多 -> ✔✔ (✅ 多方主導) (2分)
    # 若+DI >= -DI 但幾乎相同 -> ✔ (⚠️ 多方但動能不高) (1分)
    # 若+DI < -DI -> ✘ (❌ 空頭趨勢) (0分)
    if (di_p - di_m) > 5:
        checks.append({"項目": "趨勢方向 (+DI/-DI)", "狀態": "✔✔ (✅ 多方主導)", "分數": 2})
    elif di_p >= di_m:
        checks.append({"項目": "趨勢方向 (+DI/-DI)", "狀態": "✔ (⚠️ 多方但動能不高)", "分數": 1})
    else:
        checks.append({"項目": "趨勢方向 (+DI/-DI)", "狀態": "✘ (❌ 空頭趨勢)", "分數": 0})

    total_score = sum(item.get('分數', 0) for item in checks)
    signal = "BUY" if total_score >= 12 else "No BUY"

    results['判斷'] = checks
    results['總分'] = int(total_score)
    results['買賣訊號'] = signal

    return results

# --- 主程式：用戶輸入股票代碼或名稱 ---
if __name__ == "__main__":
    print("=" * 50)
    print("📈 台股技術指標分析系統")
    print("=" * 50)
    
    while True:
        user_input = input("\n請輸入股票代碼或名稱 (或輸入 'quit' 結束): ").strip()
        
        if user_input.lower() == 'quit':
            print("👋 程式結束")
            break
        
        if not user_input:
            print("❌ 請輸入有效的股票代碼或名稱")
            continue
        
        # 搜尋股票
        stock_no = search_stock(user_input)
        
        if stock_no is None:
            continue
        
        # 獲取技術指標
        print(f"\n⏳ 正在獲取 {stock_no} 的技術指標...")
        indicator_data = get_finmind_indicators(stock_no)
        
        if isinstance(indicator_data, dict):
            print(f"\n🚀 {stock_no} 最新技術指標分析報告")
            print("-" * 40)
            for key, value in indicator_data.items():
                print(f"{key:15}: {value}")
        else:
            print(f"❌ {indicator_data}")