import os
try:
    import google.generativeai as genai
except ImportError:
    genai = None

def configure_gemini():
    """
    Configures the Gemini AI model.
    It is recommended to set the GOOGLE_API_KEY environment variable.
    """
    try:
        # It's best practice to use environment variables for API keys.
        api_key = os.environ.get("GOOGLE_API_KEY")

        # 如果環境變數不存在，嘗試從 Streamlit secrets 讀取 (適合本地開發與部署)
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GOOGLE_API_KEY")
            except Exception:
                pass

        # 如果上述方式都沒找到金鑰，使用您提供的新金鑰作為備援
        if not api_key:
            api_key = "AIzaSyDzUIxXnAPAgQ4aiA06ZT1JOsiRX7bU4oY"

        if api_key and genai:
            genai.configure(api_key=api_key)
            return True
        else:
            return False
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
        return False

def format_data_for_prompt(stock_data):
    """Formats the stock data dictionary into a string for the AI prompt."""
    prompt_data = f"請針對以下「{stock_data.get('股票名稱')} ({stock_data.get('股票代號')})」的今日台股技術指標數據，提供專業的分析與投資建議。\n"
    prompt_data += "請根據布林通道、RSI、KD、ADX和成交量等指標，綜合判斷目前的多空趨勢、潛在風險與機會，並給出具體的投資策略（如：買進、賣出、持有或觀望）。\n\n"
    prompt_data += "--- 技術指標數據 ---\n"
    
    # Key-value data
    for key, value in stock_data.items():
        if key not in ['判斷', '總分', '買賣訊號', '股票代號', '股票名稱', '日期', '營收資訊', '近期新聞']:
            prompt_data += f"- {key}: {value}\n"

    prompt_data += "\n--- 硬規則判斷結果 ---\n"
    prompt_data += f"綜合分數: {stock_data.get('總分')}\n"
    prompt_data += f"簡易買賣訊號: {stock_data.get('買賣訊號')}\n"
    
    # Analysis checks
    checks = stock_data.get('判斷', [])
    if checks:
        for check in checks:
            prompt_data += f"- {check['項目']}: {check['狀態']} (分數: {check['分數']})\n"

    # Add Revenue Data
    if '營收資訊' in stock_data:
        prompt_data += "\n--- 近期月營收 (近6個月) ---\n"
        for item in stock_data['營收資訊']:
            prompt_data += f"- {item.get('date')}: {item.get('revenue')} 元\n"

    # Add News Data
    if '近期新聞' in stock_data:
        prompt_data += "\n--- 近期相關新聞 ---\n"
        for item in stock_data['近期新聞']:
            prompt_data += f"- [{item.get('date')}] {item.get('title')} (來源: {item.get('source')})\n"
            
    prompt_data += "\n--- 分析要求 ---\n"
    prompt_data += "1.  **市場趨勢分析**：這是多頭、空頭還是盤整市場？\n"
    prompt_data += "2.  **關鍵指標解讀**：BBand寬度代表什麼？RSI是否過熱或過冷？KD指標的交叉訊號是什麼？成交量是否支持目前趨勢？\n"
    prompt_data += "3.  **基本面與消息面整合**：結合近期營收表現與新聞消息，分析公司的營運狀況與市場關注焦點。\n"
    prompt_data += "4.  **SMC 關鍵區域分析 (Smart Money Concepts)**：請依照以下格式分析：\n"
    prompt_data += "    1. **市場結構 (Market Structure)**\n"
    prompt_data += "    2. **關鍵 SMC 數據點 (請指出具體價格)**\n"
    prompt_data += "       A. 看漲訂單塊 (Bullish OB) - 這裡是大戶的堡壘\n"
    prompt_data += "       B. 流動性池 (Liquidity / SSL) - 這裡是散戶的陷阱\n"
    prompt_data += "       C. 看跌失衡區 / 目標位 (Bearish FVG) - 這裡是上面的壓力\n"
    prompt_data += "    3. **SMC 操盤劇本 (Trading Plan)**\n"
    prompt_data += "       - 現價：(判斷處於 Premium/Discount/Equilibrium)\n"
    prompt_data += "       - 等待獵殺：\n"
    prompt_data += "       - 進入訂單塊：\n"
    prompt_data += "       - 進場做多：\n"
    prompt_data += "       - 目標價 (TP)：\n"
    prompt_data += "5.  **風險評估**：目前進場或持有的主要風險是什麼？\n"
    prompt_data += "6.  **投資建議**：基於技術面、基本面、消息面與SMC分析，你會建議「買進」、「賣出」、「持有」還是「等待觀察」？請說明理由。\n"

    return prompt_data

def get_ai_analysis(stock_data):
    """
    Sends stock data to Gemini AI and returns the analysis.
    """
    if genai is None:
        return "錯誤：未安裝 `google-generativeai` 套件。請在終端機執行 `pip install google-generativeai`。"

    if not configure_gemini():
        return "無法設定 Gemini AI。請檢查您的 API 金鑰是否已設定為環境變數 GOOGLE_API_KEY。"

    prompt = format_data_for_prompt(stock_data)
    
    # 根據系統偵測到的可用模型更新清單
    candidate_models = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash-exp', 'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    error_log = []

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_log.append(f"[{model_name}] {str(e)}")

    # 嘗試列出可用模型以協助除錯
    available_msg = ""
    try:
        all_models = list(genai.list_models())
        valid_models = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        available_msg = f"\n\n系統偵測到的可用模型: {', '.join(valid_models)}"
    except Exception as e:
        available_msg = f"\n\n無法列出模型 (API Key 可能無效或未啟用 API 服務): {e}"

    # 若全部失敗，回傳詳細錯誤資訊
    return (
        f"呼叫 Gemini API 失敗。\n"
        f"已嘗試模型: {', '.join(candidate_models)}\n"
        f"錯誤詳情:\n" + "\n".join(error_log) +
        available_msg
    )
