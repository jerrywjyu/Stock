
import streamlit as st
import pandas as pd
import requests
import ta
import plotly.graph_objects as go
from datetime import datetime, timedelta
import matplotlib
from twse_stock_list import fetch_twse_stock_list

matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False


st.title("台股技術指標查詢\n(均線/KD/RSI/MACD/布林通道)")



st.info("本查詢將自動抓取一年前 ~ 今日的所有資料")

# 先定義 fetch_twse_daily，再定義 get_earliest_date，避免 NameError
@st.cache_data(show_spinner=True)
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
    tables = data.get("tables", [])
    for table in tables:
        fields = table.get("fields", [])
        if "證券代號" in fields:
            rows = table.get("data", [])
            df = pd.DataFrame(rows, columns=fields)
            return df
    return pd.DataFrame()

# 取得該股票最早可查詢日期
@st.cache_data(show_spinner=True)
def get_earliest_date(stock_id):
    # 從2000年1月1日開始往後找第一筆有資料的日期
    start = datetime(2000, 1, 1)
    today = datetime.today()
    for i in range((today - start).days + 1):
        date = start + timedelta(days=i)
        if date.weekday() >= 5:
            continue
        date_str = date.strftime("%Y%m%d")
        daily_df = fetch_twse_daily(date_str)
        if daily_df is not None and "證券代號" in daily_df.columns:
            daily_df = daily_df[daily_df["證券代號"] == stock_id]
            if not daily_df.empty:
                return date
    return start

@st.cache_data(show_spinner=True)
def get_stock_options():
    df = fetch_twse_stock_list()
    # 分類字典：{產業別: [(代號 名稱), ...]}
    options = {}
    for _, row in df.iterrows():
        label = f"{row['證券代號']} {row['證券名稱']}"
        options.setdefault(row['產業別'], []).append(label)
    return options

stock_options = get_stock_options()
industry = st.selectbox('請選擇產業類別', list(stock_options.keys()))
selected_stocks = st.multiselect('請勾選股票', stock_options[industry])
stock_id_list = [s.split()[0] for s in selected_stocks]
from dateutil.relativedelta import relativedelta

# 多股票最早日期取所有股票的最早日
if stock_id_list:
    all_earliest_dates = [get_earliest_date(sid) for sid in stock_id_list]
    earliest_date = min(all_earliest_dates)
else:
    earliest_date = datetime(2000, 1, 1)
default_end = datetime.today()
default_start = default_end - relativedelta(years=1)
col_date1, col_date2 = st.columns(2)
with col_date1:
    start_date = st.date_input("起始日期", value=default_start.date(), min_value=earliest_date.date(), max_value=default_end.date())
with col_date2:
    end_date = st.date_input("結束日期", value=default_end.date(), min_value=earliest_date.date(), max_value=default_end.date())

if start_date > end_date:
    st.warning("起始日期不可大於結束日期！")

st.info(f"查詢區間：{start_date} ~ {end_date}")


# 日期區間選擇
st.info(f"查詢區間：{start_date} ~ {end_date}")

@st.cache_data(show_spinner=True)
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
    tables = data.get("tables", [])
    for table in tables:
        fields = table.get("fields", [])
        if "證券代號" in fields:
            rows = table.get("data", [])
            df = pd.DataFrame(rows, columns=fields)
            return df
    return pd.DataFrame()

def get_stock_history(stock_id, start_date, end_date):
    records = []
    stock_name = None
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.min.time())
    total_days = (end - start).days + 1
    date_list = [start + timedelta(days=i) for i in range(total_days)]

    for date in date_list:
        if date.weekday() >= 5:
            continue
        date_str = date.strftime("%Y%m%d")
        daily_df = fetch_twse_daily(date_str)
        if daily_df is None or "證券代號" not in daily_df.columns:
            continue
        daily_df = daily_df[daily_df["證券代號"] == stock_id]
        if not daily_df.empty:
            try:
                row = daily_df.iloc[0]
                if stock_name is None:
                    stock_name = row["證券名稱"]
                records.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "close": float(row["收盤價"].replace(",", "").replace('--', '0')),
                    "high": float(row["最高價"].replace(",", "").replace('--', '0')),
                    "low": float(row["最低價"].replace(",", "").replace('--', '0')),
                    "open": float(row["開盤價"].replace(",", "").replace('--', '0')),
                    "volume": float(row["成交股數"].replace(",", "").replace('--', '0')) if "成交股數" in row else None
                })
            except:
                continue
    df = pd.DataFrame(records)
    if df.empty:
        return df, stock_name
    df = df.sort_values("date")
    df.set_index("date", inplace=True)
    return df, stock_name




# 條件勾選
st.markdown("**請選擇分析條件：**")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    cond_kd = st.checkbox("%K與%D都低於20且%K上穿%D", value=False)
with col2:
    cond_vol = st.checkbox("成交量比前一天高", value=False)
with col3:
    cond_macd = st.checkbox("DIF上穿MACD", value=False)
with col4:
    cond_kd_rsi = st.checkbox("KD黃金交叉且RSI<30", value=False)
with col5:
    cond_ma_bull = st.checkbox("MA5 > MA20 > MA60 多頭排列", value=False)


# 啟動查詢按鈕
if st.button('開始查詢股票資訊'):
    for stock_id in stock_id_list:
        df, stock_name = get_stock_history(stock_id, start_date, end_date)
        if df.empty or len(df) < 5:
            st.warning(f"查無足夠資料，請確認股票代號或天數！({stock_id})")
            continue
        # 計算技術指標
        df["MA5"] = df["close"].rolling(5).mean()
        df["MA20"] = df["close"].rolling(20).mean()
        df["MA60"] = df["close"].rolling(60).mean()
        stoch = ta.momentum.StochasticOscillator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14,
            smooth_window=3
        )
        df["slowk"] = stoch.stoch()
        df["slowd"] = stoch.stoch_signal()
        rsi_indicator = ta.momentum.RSIIndicator(df["close"], window=14)
        df["RSI"] = rsi_indicator.rsi()

        # MACD
        macd_indicator = ta.trend.MACD(df["close"])
        df["MACD"] = macd_indicator.macd()
        df["MACD_signal"] = macd_indicator.macd_signal()
        df["MACD_diff"] = macd_indicator.macd_diff()

        # 布林通道
        bb_indicator = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        df["BB_upper"] = bb_indicator.bollinger_hband()
        df["BB_middle"] = bb_indicator.bollinger_mavg()
        df["BB_lower"] = bb_indicator.bollinger_lband()


        show_name = f"{stock_id} {stock_name}" if stock_name else stock_id

        # 均線圖 (Plotly)
        st.subheader(f"股價與均線 (互動) - {show_name}")

        # 條件判斷
        if cond_kd:
            kd_cross = (df["slowk"].shift(1) < df["slowd"].shift(1)) & (df["slowk"] > df["slowd"]) & (df["slowk"] < 20) & (df["slowd"] < 20)
        else:
            kd_cross = pd.Series([True]*len(df), index=df.index)
        if cond_vol:
            volume_higher = (df["volume"] > df["volume"].shift(1))
        else:
            volume_higher = pd.Series([True]*len(df), index=df.index)
        if cond_macd:
            dif_cross = (df["MACD_diff"].shift(1) < 0) & (df["MACD_diff"] > 0)
        else:
            dif_cross = pd.Series([True]*len(df), index=df.index)
        signal_cross = kd_cross & volume_higher & dif_cross
        signal_points = df[signal_cross]

        # KD黃金交叉且RSI<30標記
        kd_golden_cross = (df["slowk"].shift(1) < df["slowd"].shift(1)) & (df["slowk"] > df["slowd"]) & (df["slowk"] < 20) & (df["slowd"] < 20)
        rsi_low = df["RSI"] < 30
        kd_rsi_points = df[kd_golden_cross & rsi_low]


        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df.index, y=df["close"], mode='lines', name='收盤價', line=dict(color='black')))
        fig1.add_trace(go.Scatter(x=df.index, y=df["MA5"], mode='lines', name='5日均線', line=dict(color='blue', dash='dash')))
        fig1.add_trace(go.Scatter(x=df.index, y=df["MA20"], mode='lines', name='20日均線', line=dict(color='green', dash='dash')))
        fig1.add_trace(go.Scatter(x=df.index, y=df["MA60"], mode='lines', name='60日均線', line=dict(color='red', dash='dash')))
        # 布林通道
        fig1.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], mode='lines', name='布林上軌', line=dict(color='gray', dash='dot')))
        fig1.add_trace(go.Scatter(x=df.index, y=df["BB_middle"], mode='lines', name='布林中軌', line=dict(color='gray', dash='dash')))
        fig1.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], mode='lines', name='布林下軌', line=dict(color='gray', dash='dot')))

        # MA5 > MA20 > MA60 多頭排列標記
        if cond_ma_bull:
            ma_bull_points = df[(df["MA5"] > df["MA20"]) & (df["MA20"] > df["MA60"])]
            if not ma_bull_points.empty:
                fig1.add_trace(go.Scatter(
                    x=ma_bull_points.index,
                    y=ma_bull_points["close"],
                    mode='markers',
                    marker=dict(color='green', size=14, symbol='star-triangle-up'),
                    name='多頭排列'))

        # star-diamond 僅在有條件勾選時顯示
        if (cond_kd or cond_vol or cond_macd or cond_kd_rsi or cond_ma_bull):
            if not signal_points.empty:
                fig1.add_trace(go.Scatter(
                    x=signal_points.index,
                    y=signal_points["close"],
                    mode='markers',
                    marker=dict(color='gold', size=14, symbol='star-diamond'),
                    name='訊號成立'))
        # 標記KD黃金交叉且RSI<30的點（由勾選決定）
        if cond_kd_rsi and not kd_rsi_points.empty:
            fig1.add_trace(go.Scatter(
                x=kd_rsi_points.index,
                y=kd_rsi_points["close"],
                mode='markers',
                marker=dict(color='blue', size=14, symbol='star'),
                name='KD黃金交叉且RSI<30'))
        fig1.update_layout(title=f"{show_name} 股價與均線/布林通道", xaxis_title="日期", yaxis_title="價格 (TWD)", hovermode='x unified')
        st.plotly_chart(fig1, use_container_width=True)
        if signal_points.empty:
            st.info("目前沒有上漲訊號")

        # KD圖 (Plotly)
        st.subheader(f"KD 指標 (互動) - {show_name}")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df.index, y=df["slowk"], mode='lines', name='%K', line=dict(color='orange')))
        fig2.add_trace(go.Scatter(x=df.index, y=df["slowd"], mode='lines', name='%D', line=dict(color='purple')))
        fig2.add_hline(y=80, line_dash="dash", line_color="gray")
        fig2.add_hline(y=20, line_dash="dash", line_color="gray")
        fig2.update_layout(title=f"KD 指標 - {show_name}", hovermode='x unified')
        st.plotly_chart(fig2, use_container_width=True)

        # RSI圖 (Plotly)
        st.subheader(f"RSI 指標 (互動) - {show_name}")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode='lines', name='RSI', line=dict(color='teal')))
        fig3.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超買", annotation_position="top left")
        fig3.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超賣", annotation_position="bottom left")
        fig3.update_layout(title=f"RSI 指標 - {show_name}", hovermode='x unified')
        st.plotly_chart(fig3, use_container_width=True)

        # MACD圖 (Plotly)
        st.subheader(f"MACD 指標 (互動) - {show_name}")
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=df.index, y=df["MACD"], mode='lines', name='MACD', line=dict(color='blue')))
        fig4.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], mode='lines', name='Signal', line=dict(color='red')))
        fig4.add_trace(go.Bar(x=df.index, y=df["MACD_diff"], name='Diff', marker_color='gray', opacity=0.5))
        fig4.update_layout(title=f"MACD 指標 - {show_name}", hovermode='x unified')
        st.plotly_chart(fig4, use_container_width=True)

        st.dataframe(df, use_container_width=True)
        st.success(f"查詢完成！({show_name})")
