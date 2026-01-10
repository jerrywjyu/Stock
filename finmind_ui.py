import streamlit as st
import time
import socket
import requests
import pandas as pd
import datetime
import os
import streamlit.components.v1 as components
import json
from gemini_analyzer import get_ai_analysis
from data_storage import save_analysis_to_csv, load_analysis_history
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta
from data_storage import ANALYSIS_FILE, LOG_FILE # Import constants
from twse_stock_list import fetch_twse_stock_list


# 設定全域網路超時，避免 FinMind 請求無限期卡住
socket.setdefaulttimeout(5)

st.set_page_config(page_title="FinMind 股票查詢", layout="wide")

st.title("FinMind 股票分析平台")

# --- Session State Initialization ---
if 'last_results' not in st.session_state:
    st.session_state['last_results'] = None
if 'token_test_status' not in st.session_state:
    st.session_state['token_test_status'] = None # 'success', 'error', or None
if 'token_test_message' not in st.session_state:
    st.session_state['token_test_message'] = ""
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = []

# --- Function Definitions ---
def check_finmind_connection():
    """檢測 FinMind 伺服器連線狀態"""
    try:
        # 嘗試連線到 FinMind API 伺服器，設定 3 秒超時
        requests.get("https://api.finmindtrade.com", timeout=3)
        return True
    except Exception:
        return False

@st.cache_data(ttl=300) # 快取 5 分鐘，避免頻繁請求 API 導致被封鎖
def get_finmind_usage(token):
    """獲取 FinMind Token 使用量資訊"""
    if not token:
        return None, "Token is empty."
    try:
        url = "https://api.web.finmindtrade.com/v2/user_info"
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(url, headers=headers, timeout=5)

        if res.status_code != 200:
            return None, f"HTTP Error {res.status_code}: {res.text}"

        data = res.json()
        if data.get("status") == 200:
            # API response structure has changed, data is at the top level.
            if "api_request_limit" in data and "user_count" in data:
                return data, "Success"
            else:
                return data, "Success (no limit info)"
        else:
            return None, data.get("msg", "Unknown API Error")

    except requests.exceptions.Timeout:
        return None, "Network Timeout: Could not connect to FinMind API."
    except requests.exceptions.RequestException as e:
        return None, f"Network Request Error: {e}"
    except Exception as e:
        return None, f"An unexpected error occurred: {e}"

@st.cache_data(ttl=300) # 快取 5 分鐘
def get_finmind_indicators(stock_id, **kwargs):
    """延遲導入以避免啟動時的錯誤"""
    try:
        from FinMind_Stock import get_finmind_indicators as gfi
        return gfi(stock_id, token=kwargs.pop('token', None), **kwargs)
    except Exception as e:
        return f"錯誤：{str(e)}"

@st.cache_data
def get_cached_stock_list():
    """快取股票清單，避免重複讀取檔案"""
    return fetch_twse_stock_list()

def name_to_code(name: str) -> str:
    """根據股票名稱轉換為代碼"""
    try:
        df = get_cached_stock_list()
        match = df[df['證券名稱'].str.contains(name, na=False)]
        if not match.empty:
            return match.iloc[0]['證券代號']
    except Exception:
        pass
    return name

def get_stock_name(code: str) -> str:
    """根據股票代碼獲取名稱"""
    try:
        df = get_cached_stock_list()
        match = df[df['證券代號'] == code]
        if not match.empty:
            return match.iloc[0]['證券名稱']
    except Exception:
        pass
    return ""

def fetch_stock_data(code_input: str):
    """查詢並儲存結果到 session state"""
    query = str(code_input).strip()
    st.session_state['last_results'] = None # Reset on new query

    code = query
    if not query.isdigit():
        code = name_to_code(query)

    # 在查詢前先檢查網路，若不通則彈出通知
    if not check_finmind_connection():
        st.toast("🌐 偵測到 FinMind 伺服器連線異常，查詢可能會卡住或失敗。", icon="⚠️")

    with st.spinner(f"查詢 {code} 中..."):
        try:
            stock_name = get_stock_name(code)
            # 從 session state 取得 token
            token = st.session_state.get('finmind_token', '')
            results = get_finmind_indicators(str(code), 
                                           stock_name=stock_name if stock_name else None,
                                           token=token if token else None) # This 'token' is now primary_token
        except Exception as e:
            st.error(f"查詢失敗：{e}")
            return

    if not isinstance(results, dict):
        st.error(str(results))
        return
    
    # Store results in session state to use with AI button
    st.session_state['last_results'] = results

def render_stock_data(results):
    # --- Display main data table ---
    rows = []
    for k, v in results.items():
        if k == '判斷':
            continue
        rows.append({"指標": k, "數值": "" if v is None else str(v)})
    df_display = pd.DataFrame(rows)
    df_display['數值'] = df_display['數值'].astype(str)
    st.table(df_display)

    # --- Display analysis/rules table ---
    cond = results.get('判斷', [])
    if cond:
        cond_df = pd.DataFrame(cond)[['項目', '狀態', '分數']]
        st.markdown('**判斷項目（表格）**')
        st.table(cond_df)

        st.markdown('**判斷項目（彩色）**')
        for _, row in cond_df.iterrows():
            color = 'green' if '✔' in str(row['狀態']) else 'red'
            st.markdown(f"- **{row['項目']}**: <span style='color:{color}; font-weight:bold'>{row['狀態']}</span>", unsafe_allow_html=True)

        total_checks = int(results.get('總分', 0))
        if results.get('買賣訊號') == 'BUY':
            st.success(f"買賣訊號：BUY ({total_checks} 分)")
        else:
            st.info(f"買賣訊號：No BUY ({total_checks} 分)")

def plot_backtest_chart(df, stock_id, stock_name):
    """
    繪製回測結果圖表
    """
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, 
                        subplot_titles=('股價與指標', 'KD指標', '成交量'), 
                        row_heights=[0.5, 0.2, 0.3])

    # 1. K線圖與均線
    fig.add_trace(go.Candlestick(x=df.index,
                               open=df['Open'],
                               high=df['High'],
                               low=df['Low'],
                               close=df['Close'],
                               name='K線'), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], mode='lines', name='5日線', line=dict(width=1), hovertemplate='%{x|%Y-%m-%d} 5MA: %{y:.2f}<extra></extra>'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA10'], mode='lines', name='10日線', line=dict(width=1), hovertemplate='%{x|%Y-%m-%d} 10MA: %{y:.2f}<extra></extra>'), row=1, col=1)
    
    # 2. BBand
    fig.add_trace(go.Scatter(x=df.index, y=df['BBM'], mode='lines', name='BBand中軌(20MA)', line=dict(color='orange', width=1), hovertemplate='%{x|%Y-%m-%d} 數值: %{y:.2f}<extra></extra>'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBU'], mode='lines', name='BBand上軌', line=dict(color='gray', dash='dash', width=1), hovertemplate='%{x|%Y-%m-%d} 數值: %{y:.2f}<extra></extra>'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBL'], mode='lines', name='BBand下軌', line=dict(color='gray', dash='dash', width=1), hovertemplate='%{x|%Y-%m-%d} 數值: %{y:.2f}<extra></extra>'), row=1, col=1)

    # 3. KD指標
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], mode='lines', name='K', line=dict(color='blue', width=1), hovertemplate='%{x|%Y-%m-%d} 數值: %{y:.2f}<extra></extra>'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], mode='lines', name='D', line=dict(color='red', width=1), hovertemplate='%{x|%Y-%m-%d} 數值: %{y:.2f}<extra></extra>'), row=2, col=1)

    # 4. 標記買入點
    buy_signals_df = df[df['buy_signal']]
    if not buy_signals_df.empty:
        fig.add_trace(go.Scatter(x=buy_signals_df.index, y=buy_signals_df['High'] * 1.05, mode='markers', name='買入訊號', marker=dict(symbol='star', color='red', size=12, line=dict(color='black', width=1)), hovertemplate='%{x|%Y-%m-%d} 買入訊號<extra></extra>'), row=1, col=1)
        fig.add_trace(go.Scatter(x=buy_signals_df.index, y=buy_signals_df['K'], mode='markers', name='買入訊號', marker=dict(symbol='star', color='red', size=12, line=dict(color='black', width=1)), showlegend=False, hovertemplate='%{x|%Y-%m-%d} 買入訊號<extra></extra>'), row=2, col=1)

    # 5. 成交量 (顏色區分: 紅漲綠跌)
    colors = ['red' if row['Close'] >= row['Open'] else 'green' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量', marker_color=colors, hovertemplate='%{x|%Y-%m-%d} 量: %{y}<extra></extra>'), row=3, col=1)

    # 6. 圖表美化
    display_title = f"{stock_id} {stock_name}" if stock_name and stock_name != stock_id else stock_id
    fig.update_layout(
        title_text=f"{display_title} 回測圖表", 
        xaxis_rangeslider_visible=False, 
        height=900, 
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="股價", row=1, col=1)
    fig.update_yaxes(title_text="KD值", row=2, col=1)
    fig.update_yaxes(title_text="成交量", row=3, col=1)
    
    # 設定 X 軸日期格式
    fig.update_xaxes(
        tickformat="%Y-%m-%d",
        hoverformat="%Y-%m-%d"
    )
    return fig

@st.cache_data(show_spinner=False)
def run_backtest(stock_id: str, period_days: int, holding_days: int, use_golden_cross: bool, use_kd_range: bool, use_bb_mid: bool, use_bb_width: bool, use_bb_width_up: bool, use_rsi_range: bool, use_vol_ma: bool, token=None):
    """
    執行量化回測
    """
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        if token:
            dl.login_by_token(api_token=token)
        
        # 1. 獲取歷史數據
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=period_days)
        df = dl.taiwan_stock_daily(
            stock_id=stock_id,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        if df.empty:
            return {"error": "無法獲取該股票的歷史數據。"}

        # 將日期轉換為 datetime 並設為索引
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # 重新命名欄位以符合 ta 函式庫的慣例 (FinMind 回傳 max/min/close)
        df.columns = df.columns.str.lower()
        df = df.rename(columns={'open': 'Open', 'max': 'High', 'min': 'Low', 'close': 'Close', 'trading_volume': 'Volume'})

        # 2. 計算技術指標
        # 台股版 KD (9,3,3) 校正後算法 (遞迴法)
        df['9_high'] = df['High'].rolling(9).max()
        df['9_low'] = df['Low'].rolling(9).min()
        df['rsv'] = (df['Close'] - df['9_low']) / (df['9_high'] - df['9_low']) * 100
        df['rsv'] = df['rsv'].fillna(50)

        k_values = [50.0]
        d_values = [50.0]
        rsv_list = df['rsv'].tolist()

        for i in range(1, len(rsv_list)):
            k_cur = (2/3) * k_values[-1] + (1/3) * rsv_list[i]
            d_cur = (2/3) * d_values[-1] + (1/3) * k_cur
            k_values.append(k_cur)
            d_values.append(d_cur)

        df['K'] = k_values
        df['D'] = d_values

        # Bollinger Bands and MAs
        df['MA5'] = ta.trend.sma_indicator(df['Close'], n=5)
        df['MA10'] = ta.trend.sma_indicator(df['Close'], n=10)
        bb = ta.volatility.BollingerBands(close=df['Close'], n=20, ndev=2)
        df['BBM'] = bb.bollinger_mavg()
        df['BBU'] = bb.bollinger_hband()
        df['BBL'] = bb.bollinger_lband()
        
        # 新增指標計算
        df['BB_Width'] = (df['BBU'] - df['BBL']) / df['BBM'] * 100
        df['RSI'] = ta.momentum.rsi(df['Close'], n=14)
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()

        df = df.dropna()
        if df.empty:
            return {"error": "計算技術指標後沒有足夠數據。"}

        # 3. 尋找買入訊號
        # KD 黃金交叉
        k_col = 'K'
        d_col = 'D'
        bbm_col = 'BBM'
        
        # 初始化條件為全 True
        conditions = pd.Series(True, index=df.index)

        if use_golden_cross:
            golden_cross = (df[k_col].shift(1) < df[d_col].shift(1)) & (df[k_col] > df[d_col])
            conditions &= golden_cross
        
        if use_kd_range:
            kd_range = (df[k_col] > 40) & (df[k_col] < 50) & (df[d_col] > 40) & (df[d_col] < 50)
            conditions &= kd_range
        
        if use_bb_mid:
            # 邏輯：今日收盤突破中線，且昨日收盤在中線之下 (第一日)
            is_break = (df['Close'] > df[bbm_col])
            was_below_mid = (df['Close'].shift(1) <= df[bbm_col].shift(1))
            price_trigger_bb_mid = is_break & was_below_mid
            conditions &= price_trigger_bb_mid
            
        if use_bb_width:
            conditions &= (df['BB_Width'] < 10)
            
        if use_bb_width_up:
            conditions &= (df['BB_Width'] > df['BB_Width'].shift(1))
            
        if use_rsi_range:
            conditions &= (df['RSI'] >= 50) & (df['RSI'] <= 60)
            
        if use_vol_ma:
            conditions &= (df['Volume'] > df['Vol_MA5'])

        df['buy_signal'] = conditions

        buy_dates = df[df['buy_signal']].index
        
        # 4. 模擬交易並計算報酬
        trades = []
        for buy_date_loc in buy_dates:
            buy_price = df.loc[buy_date_loc, 'Close']
            
            # 賣出日期為持股天數之後
            sell_date_loc_index = df.index.get_loc(buy_date_loc) + holding_days
            
            if sell_date_loc_index < len(df.index):
                sell_date_loc = df.index[sell_date_loc_index]
                sell_price = df.loc[sell_date_loc, 'Close']
                trades.append({'entry_price': buy_price, 'exit_price': sell_price})

        metrics = {}
        if not trades:
            metrics = {"win_rate": 0, "total_return": 0, "trade_count": 0, "message": "在指定條件下沒有任何交易。"}
        else:
            # 5. 計算勝率與總報酬
            win_count = sum(1 for trade in trades if trade['exit_price'] > trade['entry_price'])
            total_return_pct = sum(((trade['exit_price'] - trade['entry_price']) / trade['entry_price']) for trade in trades)
            win_rate = (win_count / len(trades)) * 100
            metrics = {"win_rate": win_rate, "total_return": total_return_pct * 100, "trade_count": len(trades)}
        
        return {"metrics": metrics, "dataframe": df}
    except Exception as e:
        return {"error": f"回測時发生錯誤：{e}"}



def display_analysis_history():
    """顯示儲存的分析歷史紀錄"""
    st.header("📜 歷史分析紀錄 (V2)")

    if st.button("🔄 重新讀取並顯示 analysis_history.csv"):
        try:
            # 直接從檔案讀取以進行驗證
            history_df = pd.read_csv('analysis_history.csv')
            st.subheader("analysis_history.csv 原始資料")
            st.dataframe(history_df)
            st.success("成功讀取並顯示 analysis_history.csv")
        except FileNotFoundError:
            st.error("analysis_history.csv 檔案不存在。")
        except Exception as e:
            st.error(f"讀取 CSV 檔案時發生錯誤：{e}")
    
    st.markdown("---")

    # 使用 data_storage 中的函數來載入歷史紀錄
    df = load_analysis_history(limit=500) # 載入最新的 500 筆

    if df.empty:
        st.info("目前沒有任何歷史分析紀錄。請在「技術指標查詢」頁面進行分析後，紀錄將會顯示於此。")
        return

    try:
        # 讓使用者可以依股票代碼篩選
        all_stocks = df['StockID'].unique()
        selected_stock = st.selectbox("選擇要查看的股票", ["全部"] + list(all_stocks))

        if selected_stock != "全部":
            df_display = df[df['StockID'] == selected_stock]
        else:
            df_display = df

        # 顯示篩選後的 DataFrame，確保欄位順序和名稱正確
        st.dataframe(df_display[['Date', 'StockID', 'StockName', 'Analysis']])

        st.markdown("---")
        st.subheader("詳細紀錄")

        if df_display.empty:
            st.write("此篩選條件下無紀錄。")
            return

        # 確保迭代前 'Date' 欄位是字串格式以避免顯示問題
        df_display['Date'] = df_display['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')

        for _, row in df_display.iterrows():
            with st.expander(f"{row['Date']} - {row['StockID']} {row['StockName']}"):
                st.markdown("**AI 分析結果：**")
                st.markdown(row['Analysis'])

    except Exception as e:
        st.error(f"讀取歷史紀錄時發生錯誤：{e}")


# --- Sidebar: Token Management ---
st.sidebar.header("🔑 API 設定")

# 預設使用您提供的 Token，也可以從 Streamlit Secrets 讀取
default_token = st.secrets.get("FINMIND_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMS0wOCAxMDowMjoxMiIsInVzZXJfaWQiOiJKZXJyeSIsImVtYWlsIjoieXVfd2VuX2NoaWVoQGhvdG1haWwuY29tIiwiaXAiOiIxMTEuMjQwLjE1Ni40MyJ9.hm0gxcyfks_Pe35XyBo8-1wRV6ZLcDLwr6gd0Z3cWtc")

# 使用 on_change 回調來清除之前的測試訊息
def on_token_change():
    st.session_state['token_test_status'] = None
    st.session_state['token_test_message'] = ""

fm_token = st.sidebar.text_input("FinMind Token", value=default_token, type="password",
                                 help="輸入您的 FinMind API Token 以獲得更高的使用限額", key="finmind_token",
                                 on_change=on_token_change)

if fm_token:
    usage_info, msg = get_finmind_usage(fm_token)
    if usage_info and msg == "Success":
        # Based on new API response, 'user_count' is the usage count.
        count = usage_info.get("user_count", 0)
        limit = usage_info.get("api_request_limit", 0)
        remaining = limit - count
        
        st.sidebar.subheader("📊 Token 使用狀態")
        st.sidebar.metric("已使用次數", count)
        st.sidebar.metric("總額度", limit)
        st.sidebar.metric("剩餘次數", remaining)
        
        # Progress bar should show used/limit
        progress_value = (count / limit) if limit > 0 else 0
        st.sidebar.progress(max(0, min(1.0, progress_value)))
    elif usage_info and msg == "Success (no limit info)":
        count = usage_info.get("user_count")
        st.sidebar.subheader("📊 Token 使用狀態")
        if count is not None:
            st.sidebar.metric("已使用次數", count)
        st.sidebar.info("此 Token 無額度限制資訊。")
    else:
        if msg == "Network Timeout: Could not connect to FinMind API.":
            st.sidebar.warning("🌐 連線逾時，無法取得 Token 資訊。請檢查網路或稍後再試。")
        elif msg == "Token is empty.":
            st.sidebar.info("請輸入您的 FinMind Token。")
        else:
            st.sidebar.error(f"❌ 無法取得 Token 資訊：{msg}。請檢查 Token 是否正確。")

# 顯示持久化的 Token 測試結果
if st.session_state['token_test_status'] == 'success':
    st.sidebar.success(st.session_state['token_test_message'])
elif st.session_state['token_test_status'] == 'error':
    st.sidebar.error(st.session_state['token_test_message'])

# 新增一個明確的 Token 測試按鈕
if st.sidebar.button("測試 Token", key="test_token_button"):
    # 清除快取以確保進行全新的 API 呼叫
    get_finmind_usage.clear()
    # 清除之前的測試訊息
    st.session_state['token_test_status'] = None
    st.session_state['token_test_message'] = ""

    test_usage_info, test_msg = get_finmind_usage(fm_token)
    if test_usage_info:
        st.session_state['token_test_status'] = 'success'
        st.session_state['token_test_message'] = "✅ Token 測試成功！"
    else:
        st.session_state['token_test_status'] = 'error'
        st.session_state['token_test_message'] = f"❌ Token 測試失敗：{test_msg}"
    st.rerun() # 重新執行腳本以更新 Token 狀態顯示
if st.sidebar.button("🔄 重新整理 Token 狀態"):
    get_finmind_usage.clear() # 清除快取
    st.rerun() # 重新執行腳本以更新狀態

# --- UI Layout ---
# Use a radio button as a stateful tab controller to prevent switching back on rerun. Update tab title.
tab_options = ["📊 技術指標查詢", "📈 策略量化回測", "🔍 選股條件搜尋", "❤️ 我的自選股", "📜 歷史分析紀錄 (V2)"]
selected_tab = st.radio("選擇功能", tab_options, horizontal=True, label_visibility="collapsed")

if selected_tab == "📊 技術指標查詢":
    st.header("FinMind 股票技術指標查詢")
    st.write("輸入股票代碼（如 2497）或股票名稱（如 怡利電），按下「查詢」取得最新技術指標。")
    stock_input = st.text_input("股票代號或名稱", value="2497", key="stock_input")

    if st.button("🔍 查詢", key="query_button"):
        # 清除快取，確保查詢到的是最新資料
        get_finmind_indicators.clear()
        fetch_stock_data(st.session_state.get('stock_input', ''))

    if st.session_state.get('last_results'):
        results = st.session_state['last_results']
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.success(f"{results.get('股票代號')} {results.get('股票名稱')} 查詢完成（{results.get('日期')}）")
            with st.expander("📊 技術指標數據", expanded=True):
                render_stock_data(results)

            # Add to watchlist button
            stock_code_to_add = results.get('股票代號')
            if stock_code_to_add:
                if st.button("❤️ 加入自選", key=f"add_{stock_code_to_add}"):
                    if stock_code_to_add not in st.session_state.watchlist:
                        st.session_state.watchlist.append(stock_code_to_add)
                        st.toast(f"已將 {stock_code_to_add} {results.get('股票名稱')} 加入自選股！")
                    else:
                        st.toast(f"{stock_code_to_add} 已經在您的自選股清單中了。")
                
        with col2:
            st.markdown("### 📝 我的註解與行情預測")
            user_note = st.text_area("您可以在此輸入您對該股的觀察、新聞重點或隔日走勢預測，AI會將此資訊納入考量。", height=150, key="user_note_input")

            st.markdown("### 🤖 AI 智慧分析")
            if st.button("開始分析", key="analyze_button"):
                with st.spinner("🤖 正在進行分析..."):
                    analysis_data = st.session_state['last_results'].copy()
                    
                    # Add the user's note to the analysis data
                    if user_note:
                        analysis_data['使用者註解'] = user_note

                    ai_response = get_ai_analysis(analysis_data)
                    st.markdown(ai_response) # Display the response first

                    # After getting the response, save it
                    if ai_response and "呼叫 Gemini API 失敗" not in ai_response:
                        stock_id = st.session_state['last_results'].get('股票代號')
                        stock_name = st.session_state['last_results'].get('股票名稱')
                        
                        save_success, message = save_analysis_to_csv(stock_id, stock_name, ai_response)
                        if save_success:
                            st.toast("✅ 分析結果已成功儲存！")
                        else:
                            st.toast(f"⚠️ 儲存失敗: {message}")

                        # Add a copy-to-clipboard button
                        escaped_response = json.dumps(ai_response)
                        components.html(f'''
                            <div style="display: flex; justify-content: flex-end; margin-bottom: -60px; margin-top: 10px;">
                                <button id="copy-btn" style="padding: 5px 10px; border-radius: 5px; border: 1px solid #ccc; background-color: #f0f0f0; cursor: pointer;">📋 複製</button>
                            </div>
                            <script>
                                document.getElementById('copy-btn').addEventListener('click', function() {{
                                    navigator.clipboard.writeText({escaped_response}).then(() => {{
                                        this.innerText = '✅ 已複製!';
                                        setTimeout(() => {{ this.innerText = '📋 複製'; }}, 2000);
                                    }}).catch(err => {{
                                        console.error('Failed to copy: ', err);
                                        this.innerText = '複製失敗';
                                    }});
                                }});
                            </script>
                        ''', height=40)

elif selected_tab == "📈 策略量化回測":
    st.header("策略量化回測")
    st.write("請勾選回測條件（多選為 AND 條件）：")
    
    use_golden_cross = st.checkbox("KD 指標黃金交叉 (當日 K > D, 昨日 K < D)", value=False)
    use_kd_range = st.checkbox("K 值與 D 值皆介於 40 至 50 之間", value=False)
    use_bb_mid = st.checkbox("股價從中線以下突破中線 (僅限第一日)", value=False)
    use_bb_width = st.checkbox("BBand 寬度 % < 10 (代表盤整壓縮)", value=False)
    use_rsi_range = st.checkbox("RSI 介於 50 至 60 之間 (代表強勢起漲)", value=False)
    use_vol_ma = st.checkbox("成交量 > 5 日均量 (代表量增)", value=False)
    use_bb_width_up = st.checkbox("BBand 寬度上揚", value=False)

    backtest_stock_input = st.text_input("輸入要回測的股票代號或名稱", value="2330", key="backtest_stock_input")
    
    period_mapping = {
        "2年": 730,
        "18個月": 547,
        "1年": 365,
        "半年": 182,
        "3個月": 91,
        "2個月": 61,
        "1個月": 30
    }
    period_option = st.selectbox("選擇回測期間", list(period_mapping.keys()))
    
    holding_days = st.number_input("持股天數 (賣出條件)", min_value=1, value=10)

    if st.button("🚀 開始回測", key="backtest_button"):
        query = str(backtest_stock_input).strip()
        code = query
        if not query.isdigit():
            code = name_to_code(query)
        
        if not code or not code.isdigit():
            st.error(f"找不到股票代碼： {query}")
        else:
            stock_name = get_stock_name(code)
            display_label = f"{code} {stock_name}" if stock_name and stock_name != code else code
            
            with st.spinner(f"正在對 {display_label} 進行回測..."):
                period_days = period_mapping[period_option]
                current_token = st.session_state.get('finmind_token', '')
                backtest_results = run_backtest(code, period_days, holding_days, 
                                              use_golden_cross, use_kd_range, use_bb_mid, use_bb_width, use_bb_width_up, use_rsi_range, use_vol_ma,
                                              token=current_token if current_token else None) # This 'token' is now primary_token

                if "error" in backtest_results:
                    st.error(backtest_results["error"])
                else:
                    metrics = backtest_results["metrics"]
                    df_chart = backtest_results["dataframe"]

                    if "message" in metrics:
                        st.info(metrics["message"])
                        st.metric("總交易次數", 0)
                        st.metric("勝率", "0.00%")
                        st.metric("總報酬率", "0.00%")
                    else:
                        st.success(f"回測完成！ 股票：{display_label}")
                        col1, col2, col3 = st.columns(3)
                        col1.metric("總交易次數", f"{metrics['trade_count']} 次")
                        col2.metric("勝率", f"{metrics['win_rate']:.2f}%")
                        col3.metric("總報酬率", f"{metrics['total_return']:.2f}%")
                    
                    if not df_chart.empty:
                        fig = plot_backtest_chart(df_chart, code, stock_name)
                        st.plotly_chart(fig, use_container_width=True)

elif selected_tab == "🔍 選股條件搜尋":
    st.header("選股條件搜尋")

    # 獲取股票清單以提取產業別
    try:
        df_all_stocks = fetch_twse_stock_list()
        # 過濾掉權證與非 4 位數代碼的標的
        df_all_stocks = df_all_stocks[df_all_stocks['證券代號'].str.len() == 4]
        
        # 從完整清單中提取產業別用於下拉選單
        df_industries = df_all_stocks.dropna(subset=['產業別'])
        df_industries = df_industries[df_industries['產業別'].str.strip() != '']
        all_industries = sorted(df_industries['產業別'].unique().tolist())
    except Exception as e:
        st.error(f"無法獲取股票清單：{e}")
        df_all_stocks = pd.DataFrame()
        all_industries = []

    st.write("請設定搜尋條件：")
    selected_industries = st.multiselect("篩選產業別 (不選則搜尋全部上市股票)", all_industries)

    st.subheader("指標過濾條件 (多選為 AND 條件)")
    
    # 分組 1: 價格與趨勢
    with st.container(border=True):
        st.write("**📈 價格與趨勢**")
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            s_price_limit = st.checkbox("1. 股價低於設定值", value=False)
            s_above_ma5 = st.checkbox("2. 股價在 5 日線之上", value=False)
            s_above_bb_mid = st.checkbox("3. 股價從中線以下突破中線 (僅限第一日)", value=False)
            s_bb_width_limit = st.checkbox("4. BBand 寬度 % <= 設定值", value=False)
            s_bb_width_up = st.checkbox("11. BBand 寬度上揚", value=False)
        with col2:
            price_val = st.number_input("股價上限", value=80.0, step=1.0, key="p_val")
            st.write("") # 佔位對齊
            st.write("")
            bb_width_val = st.number_input("布林寬度上限", value=10.0, step=0.5, key="bbw_val")

    # 分組 2: 技術指標
    with st.container(border=True):
        st.write("**📊 技術指標 (RSI / KD)**")
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            s_rsi_range = st.checkbox("5. RSI 介於設定區間且上揚", value=False)
            s_kd_limit = st.checkbox("6. KD 值皆大於設定值且 KD 上揚", value=False)
            s_k_above_d = st.checkbox("7. K > D (黃金交叉狀態)", value=False)
        with col2:
            rsi_min = st.number_input("RSI 下限", value=50.0, step=1.0, key="rsi_min")
            kd_val = st.number_input("KD 門檻值", value=30.0, step=1.0, key="kd_val")
        with col3:
            rsi_max = st.number_input("RSI 上限", value=60.0, step=1.0, key="rsi_max")

    # 分組 3: 成交量與動能
    with st.container(border=True):
        st.write("**🔊 成交量與動能 (ADX / DI)**")
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            s_vol_ma = st.checkbox("8. 成交量 > 5 日均量", value=False)
            s_di_cross = st.checkbox("9. +DI > -DI", value=False)
            s_adx_limit = st.checkbox("10. ADX > 設定值且 ADX 上揚", value=False)
        with col2:
            st.write("") # 佔位
            st.write("")
            adx_val = st.number_input("ADX 門檻值", value=20.0, step=1.0, key="adx_val")

    exclude_no_industry = st.checkbox("排除無產業別的股票", value=True, help="若取消勾選，將包含產業別為空值的股票一併搜尋。")

    if st.button("🚀 開始搜尋符合條件的股票", key="scanner_button"):
        if df_all_stocks.empty:
            st.error("股票清單為空，無法搜尋。")
        else:
            start_time = datetime.datetime.now()
            df_stocks = df_all_stocks.copy()
            
            # Apply filters based on UI selections
            if selected_industries:
                df_stocks = df_stocks[df_stocks['產業別'].isin(selected_industries)]
            elif exclude_no_industry:
                # This applies only when no specific industry is selected
                df_stocks = df_stocks.dropna(subset=['產業別'])
                df_stocks = df_stocks[df_stocks['產業別'].str.strip() != '']
            
            results_found = []
            total_stocks = len(df_stocks)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 掃描前檢查網路
            if not check_finmind_connection():
                st.error("❌ 無法連線至 FinMind 伺服器，請檢查您的網路連線或稍後再試。")
                st.stop()

            # 封裝參數供執行緒使用
            params = {
                "s_price_limit": s_price_limit, "price_val": price_val,
                "s_above_ma5": s_above_ma5,
                "s_above_bb_mid": s_above_bb_mid,
                "s_bb_width_limit": s_bb_width_limit, "bb_width_val": bb_width_val,
                "s_bb_width_up": s_bb_width_up,
                "s_rsi_range": s_rsi_range, "rsi_min": rsi_min, "rsi_max": rsi_max,
                "s_kd_limit": s_kd_limit, "kd_val": kd_val,
                "s_k_above_d": s_k_above_d,
                "s_vol_ma": s_vol_ma,
                "s_di_cross": s_di_cross,
                "s_adx_limit": s_adx_limit, "adx_val": adx_val
            }
            
            current_token = st.session_state.get('finmind_token', '')

            def check_stock(row):
                sid = row['證券代號']
                sname = row['證券名稱']
                # 傳入 sname 避免 get_finmind_indicators 內部再去讀取 CSV 檔案
                stock_data = get_finmind_indicators(sid, stock_name=sname, token=current_token if current_token else None) # This 'token' is now primary_token
                if not isinstance(stock_data, dict):
                    return None
                
                current_price = stock_data.get("今日股價", 0)
                yesterday_close = stock_data.get("昨日收盤價", 0)
                price_change_percent = 0.0
                if yesterday_close != 0:
                    price_change_percent = ((current_price - yesterday_close) / yesterday_close) * 100

                match = True
                if params["s_price_limit"] and not (stock_data.get("今日股價", 0) < params["price_val"]): match = False
                if params["s_above_ma5"] and not (stock_data.get("今日股價", 0) > stock_data.get("MA5", 0)): match = False
                if params["s_above_bb_mid"]:
                    current_price_bb_mid = stock_data.get("今日股價", 0)
                    current_bb_mid = stock_data.get("BBand 中軌 (20MA)", 0)
                    previous_close_bb_mid = stock_data.get("昨日收盤價", 0)
                    previous_bb_mid = stock_data.get("昨日 BBand 中軌", 0)
                    if not (current_price_bb_mid > current_bb_mid and previous_close_bb_mid <= previous_bb_mid): match = False
                if params["s_bb_width_limit"] and not (stock_data.get("BBand 寬度 (%)", 100) <= params["bb_width_val"]): match = False
                if params["s_bb_width_up"] and not (stock_data.get("BBand 寬度 (%)", 0) > stock_data.get("昨日 BBand 寬度", 0)): match = False
                if params["s_rsi_range"] and not (params["rsi_min"] < stock_data.get("RSI (14)", 0) < params["rsi_max"] and stock_data.get("RSI (14)", 0) > stock_data.get("昨日 RSI (14)", 0)): match = False
                if params["s_kd_limit"] and not (stock_data.get("K值(9, 3)-校正後", 0) > params["kd_val"] and stock_data.get("D值(9, 3)-校正後", 0) > params["kd_val"] and stock_data.get("K值(9, 3)-校正後", 0) > stock_data.get("昨日 K值", 0) and stock_data.get("D值(9, 3)-校正後", 0) > stock_data.get("昨日 D值", 0)): match = False
                if params["s_k_above_d"] and not (stock_data.get("K值(9, 3)-校正後", 0) > stock_data.get("D值(9, 3)-校正後", 0)): match = False
                if params["s_vol_ma"] and not (stock_data.get("今日成交量 (張)", 0) > stock_data.get("5 日均量 (張)", 0)): match = False
                if params["s_di_cross"] and not (stock_data.get("+DI", 0) > stock_data.get("-DI", 0)): match = False
                if params["s_adx_limit"] and not (stock_data.get("ADX", 0) > params["adx_val"] and stock_data.get("ADX", 0) > stock_data.get("昨日 ADX", 0)): match = False
                
                if match:
                    return {
                        "代號": sid,
                        "名稱": sname,
                        "產業別": row['產業別'],
                        "漲跌幅價格": f"{price_change_percent:.2f}%",
                        "現價": stock_data.get("今日股價"),
                        "RSI(14)": stock_data.get("RSI (14)"),
                        "ADX": stock_data.get("ADX"),
                        "成交量(張)": stock_data.get("今日成交量 (張)"),
                        "5日均量": stock_data.get("5 日均量 (張)")
                    }
                return None

            # 改回單執行緒掃描
            for i, (_, row) in enumerate(df_stocks.iterrows()):
                # 更新進度條與狀態文字
                progress = (i + 1) / total_stocks
                progress_bar.progress(progress)
                status_text.text(f"正在掃描 ({i+1}/{total_stocks}): {row['證券代號']} {row['證券名稱']}")
                
                # 每掃描 50 檔檢查一次網路狀態，避免在斷網情況下無謂等待
                if i % 50 == 0 and i > 0:
                    if not check_finmind_connection():
                        st.error(f"❌ 掃描中斷：偵測到網路連線中斷。已完成 {i} 檔。")
                        break

                try:
                    res = check_stock(row)
                    if res:
                        results_found.append(res)
                    # 避免請求過快導致被封鎖，加入微小延遲
                    time.sleep(6)
                except Exception as e:
                    print(f"Error scanning {row['證券代號']}: {e}")
                    pass
            
            progress_bar.empty()
            status_text.empty()
            
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if results_found:
                st.success(f"搜尋完成！共找到 {len(results_found)} 檔符合條件的股票。 (總耗時: {duration:.2f} 秒)")
                res_df = pd.DataFrame(results_found)
                st.dataframe(res_df, use_container_width=True)
                
                # 提供 CSV 下載
                csv = res_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 下載搜尋結果 CSV", data=csv, file_name=f"stock_scan_{datetime.date.today()}.csv", mime="text/csv")
            else:
                st.info(f"搜尋完成，目前沒有符合所有勾選條件的股票。 (總耗時: {duration:.2f} 秒)")

elif selected_tab == "❤️ 我的自選股":
    st.header("❤️ 我的自選股")

    if not st.session_state.watchlist:
        st.info("您的自選股清單目前是空的。請在「技術指標查詢」分頁中找到股票後，點擊「❤️ 加入自選」按鈕來新增。")
    else:
        if st.button("🔄 全部更新", key="refresh_watchlist"):
            # Clear cache for indicators to force a refresh
            get_finmind_indicators.clear()
            st.toast("自選股已全部更新！")
            st.rerun()
            
        st.markdown("---")

        # Create a copy for safe iteration while removing items
        watchlist_copy = st.session_state.watchlist[:]
        
        for stock_code in watchlist_copy:
            stock_name = get_stock_name(stock_code)
            
            # Use columns for layout
            col1, col2 = st.columns([4, 1])

            with col1:
                st.subheader(f"{stock_code} {stock_name}")
            with col2:
                if st.button("🗑️ 移除", key=f"remove_{stock_code}", use_container_width=True):
                    st.session_state.watchlist.remove(stock_code)
                    st.toast(f"已從自選股移除 {stock_code} {stock_name}。")
                    st.rerun()

            # Fetch data for this stock
            data = get_finmind_indicators(stock_code, stock_name=stock_name, token=st.session_state.get('finmind_token', ''))

            if isinstance(data, dict):
                c1, c2, c3 = st.columns(3)
                price = data.get('今日股價', 0)
                prev_close = data.get('昨日收盤價', 0)
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close != 0 else 0
                
                price_color = "red" if change > 0 else "green" if change < 0 else "gray"
                
                with c1:
                    st.markdown(f"**股價**")
                    st.markdown(f"<h4 style='color:{price_color};'>{price:,.2f}</h4>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:{price_color};'>({change:+.2f} / {change_pct:+.2f}%)</span>", unsafe_allow_html=True)

                with c2:
                    st.markdown(f"**關鍵指標**")
                    st.text(f"RSI(14): {data.get('RSI (14)', 'N/A')}")
                    st.text(f"K/D: {round(data.get('K值(9, 3)-校正後', 0), 2)} / {round(data.get('D值(9, 3)-校正後', 0), 2)}")

                with c3:
                    st.markdown(f"**成交與布林**")
                    st.text(f"量: {data.get('今日成交量 (張)', 'N/A'):,} 張")
                    st.text(f"BBand: {data.get('BBand 下限', 'N/A')} - {data.get('BBand 上限', 'N/A')}")

            else:
                st.error(f"無法取得 {stock_code} 的資料: {data}")
            
            st.markdown("---")
