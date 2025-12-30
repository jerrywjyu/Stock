import streamlit as st
import pandas as pd
import datetime
from gemini_analyzer import get_ai_analysis
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta
from twse_stock_list import fetch_twse_stock_list

st.set_page_config(page_title="FinMind 股票查詢", layout="wide")

st.title("FinMind 股票分析平台")

# --- Session State Initialization ---
if 'last_results' not in st.session_state:
    st.session_state['last_results'] = None

# --- Function Definitions ---
def get_finmind_indicators(stock_id):
    """延遲導入以避免啟動時的錯誤"""
    try:
        from FinMind_Stock import get_finmind_indicators as gfi
        return gfi(stock_id)
    except Exception as e:
        return f"錯誤：{str(e)}"

def name_to_code(name: str) -> str:
    """根據股票名稱轉換為代碼"""
    try:
        df = fetch_twse_stock_list()
    except Exception:
        return name
    
    match = df[df['證券名稱'].str.contains(name, na=False)]
    if not match.empty:
        return match.iloc[0]['證券代號']
    return name

def get_stock_name(code: str) -> str:
    """根據股票代碼獲取名稱"""
    try:
        df = fetch_twse_stock_list()
    except Exception:
        return ""
    
    match = df[df['證券代號'] == code]
    if not match.empty:
        return match.iloc[0]['證券名稱']
    return ""

def fetch_stock_data(code_input: str):
    """查詢並儲存結果到 session state"""
    query = str(code_input).strip()
    st.session_state['last_results'] = None # Reset on new query

    code = query
    if not query.isdigit():
        code = name_to_code(query)

    with st.spinner(f"查詢 {code} 中..."):
        try:
            results = get_finmind_indicators(str(code))
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

@st.cache_data
def run_backtest(stock_id: str, period_days: int, holding_days: int, use_golden_cross: bool, use_kd_range: bool, use_bb_mid: bool):
    """
    執行量化回測
    """
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        
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
            price_near_bb_mid = (df['Close'] >= df[bbm_col] * 0.99) & (df['Close'] <= df[bbm_col] * 1.01)
            conditions &= price_near_bb_mid
            
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

# --- UI Layout ---
tab1, tab2 = st.tabs(["📊 技術指標查詢", "📈 策略量化回測"])

with tab1:
    st.header("FinMind 股票技術指標查詢")
    st.write("輸入股票代碼（如 2497）或股票名稱（如 怡利電），按下「查詢」取得最新技術指標。")
    stock_input = st.text_input("股票代號或名稱", value="2497", key="stock_input")

    if st.button("🔍 查詢", key="query_button"):
        fetch_stock_data(st.session_state.get('stock_input', ''))

    if st.session_state.get('last_results'):
        results = st.session_state['last_results']
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.success(f"{results.get('股票代號')} {results.get('股票名稱')} 查詢完成（{results.get('日期')}）")
            with st.expander("📊 技術指標數據", expanded=True):
                render_stock_data(results)
                
        with col2:
            st.markdown("### 🤖 AI 智慧分析")
            if st.button("開始分析", key="analyze_button"):
                with st.spinner("🤖 正在蒐集新聞與營收資料並進行分析..."):
                    analysis_data = st.session_state['last_results'].copy()
                    
                    # 嘗試取得 FinMind 額外資訊 (營收與新聞)
                    try:
                        from FinMind.data import DataLoader
                        dl = DataLoader()
                        stock_id = analysis_data.get('股票代號')
                        today = datetime.date.today()
                        
                        # 取得近 6 個月營收
                        start_date_rev = (today - datetime.timedelta(days=200)).strftime('%Y-%m-%d')
                        rev_df = dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date_rev)
                        if not rev_df.empty:
                            analysis_data['營收資訊'] = rev_df.sort_values('date').tail(6).to_dict('records')
                        
                        # 取得近 1 個月新聞
                        start_date_news = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                        news_df = dl.taiwan_stock_news(stock_id=stock_id, start_date=start_date_news)
                        if not news_df.empty:
                            analysis_data['近期新聞'] = news_df.tail(10).to_dict('records')
                    except Exception as e:
                        print(f"FinMind Data Error: {e}")

                    ai_response = get_ai_analysis(analysis_data)
                    
                    st.markdown(ai_response)

with tab2:
    st.header("策略量化回測")
    st.write("請勾選回測條件（多選為 AND 條件）：")
    
    use_golden_cross = st.checkbox("KD 指標黃金交叉 (當日 K > D, 昨日 K < D)", value=True)
    use_kd_range = st.checkbox("K 值與 D 值皆介於 40 至 50 之間", value=True)
    use_bb_mid = st.checkbox("當日收盤價在布林通道中線 (20MA) 的 ±1% 範圍內", value=True)

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
                backtest_results = run_backtest(code, period_days, holding_days, use_golden_cross, use_kd_range, use_bb_mid)

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
