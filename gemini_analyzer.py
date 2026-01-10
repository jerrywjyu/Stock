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
        # The new google-genai library recommends GEMINI_API_KEY.
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        # 如果環境變數不存在，嘗試從 Streamlit secrets 讀取 (適合本地開發與部署)
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GOOGLE_API_KEY")
            except Exception:
                pass

        # 如果上述方式都沒找到金鑰，則返回失敗
        if not api_key:
            return False

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

    # Add user's note if it exists
    if '使用者註解' in stock_data and stock_data['使用者註解']:
        prompt_data += "--- 使用者註解與預測 ---\n"
        prompt_data += f"{stock_data['使用者註解']}\n"
        prompt_data += "請務必將此註解內容納入考量，並與技術面數據進行比較分析。\n\n"

    prompt_data += "--- 技術指標數據 ---\n"
    
    # Key-value data
    for key, value in stock_data.items():
        if key not in ['判斷', '總分', '買賣訊號', '股票代號', '股票名稱', '日期', '營收資訊', '近期新聞', '使用者註解']:
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
    prompt_data += "1. **市場趨勢判斷**\n"
    prompt_data += "- 目前屬於：多頭 / 空頭 / 盤整\n"
    prompt_data += "- 判斷依據（結構高低點、均線、趨勢線）\n"
    prompt_data += "- 趨勢是否健康？是否有轉弱跡象？\n"

    prompt_data += "2. **技術指標解讀**\n"
    prompt_data += "- BBand 寬度：代表波動率擴張或收斂？\n"
    prompt_data += "- RSI：是否過熱 / 過冷？是否背離？\n"
    prompt_data += "- KD：是否出現黃金 / 死亡交叉？有效性如何？\n"
    prompt_data += "- 成交量：是否支持目前價格行為？\n"

    prompt_data += "3. **基本面與消息面**\n"
    prompt_data += "- 近期營收與成長性評估\n"
    prompt_data += "- 新聞是否為短期題材或中長期利多 / 利空？\n"
    prompt_data += "- 市場目前關注焦點是「成長 / 修正 / 不確定性」？\n"

    prompt_data += "4. **Smart Money Concepts 分析**\n"
    prompt_data += "4.1 市場結構（Market Structure）\n"
    prompt_data += "- 高週期結構（HTF）：多 / 空\n"
    prompt_data += "- 是否出現 MSS / CHoCH？\n"
    prompt_data += "4.2 關鍵 SMC 價格區\n"
    prompt_data += "A. 看漲訂單塊（Bullish OB）：\n"
    prompt_data += "   - 價格區間：\n"
    prompt_data += "   - 形成背景與合理性：\n"
    prompt_data += "B. 流動性池（Liquidity / SSL / BSL）：\n"
    prompt_data += "   - 可能被獵殺的價位：\n"
    prompt_data += "   - 散戶常見誤區：\n"
    prompt_data += "C. 看跌失衡區 / 目標位（Bearish FVG）：\n"
    prompt_data += "   - 價格區間：\n"
    prompt_data += "   - 是否為潛在壓力或獲利了結區：\n"
    prompt_data += "4.3 價值區判斷\n"
    prompt_data += "- 現價位於：Premium / Discount / Equilibrium\n"

    prompt_data += "5. **多時間框架分析**\n"
    prompt_data += "- 高週期（日 / 週）：主要方向\n"
    prompt_data += "- 中週期（4H / 1H）：關鍵結構與 OB\n"
    prompt_data += "- 低週期（15m / 5m）：進出場觸發\n"

    prompt_data += "6. **SMC 操盤劇本**\n"
    prompt_data += "- 主要劇本（Main Scenario）：\n"
    prompt_data += "  - 等待獵殺：\n"
    prompt_data += "  - 進入訂單塊：\n"
    prompt_data += "  - 進場方向（多 / 空）：\n"
    prompt_data += "  - 停損（SL）：\n"
    prompt_data += "  - 目標價（TP1 / TP2）：\n"
    prompt_data += "- 備用劇本（Alternative Scenario）：\n"
    prompt_data += "  - 若結構被破壞，該如何應對？\n"

    prompt_data += "7. **交易設定品質評分（0–100）**\n"
    prompt_data += "- 趨勢一致性：\n"
    prompt_data += "- 流動性條件完成度：\n"
    prompt_data += "- OB / FVG 精準度：\n"
    prompt_data += "- 成交量配合度：\n"
    prompt_data += "- 風險報酬比（RR）：\n"
    prompt_data += "8. **主要風險**\n"
    prompt_data += "- 技術面失效風險\n"
    prompt_data += "- 基本面不確定性\n"
    prompt_data += "- 重大事件（財報 / 法說 / 總經數據）\n"

    prompt_data += "9. **止跌與轉折跡象判斷**：\n"
    prompt_data += "- 請以『尚未止跌 / 初步止跌 / 已確認止跌』三選一作答，並說明理由。\n"

    prompt_data += "10. **投資建議（擇一）**\n"
    prompt_data += "- 買進 / 賣出 / 持有 / 等待觀察\n"
    prompt_data += "請用「一句話結論 + 3 個關鍵理由」說明。\n"

    prompt_data += "- 若是持有狀態，應如何處置:\n"
    prompt_data += "- 請給出具體的買賣點位建議（若適用）\n"

    return prompt_data

def get_ai_analysis(stock_data):
    """
    Sends stock data to Gemini AI and returns the analysis.
    It tries a list of models in order until one succeeds.
    """
    if genai is None:
        return "錯誤：未安裝 `google-genai` 套件。請在終端機執行 `pip install google-genai`。"

    if not configure_gemini():
        return "無法設定 Gemini AI。請檢查您的 API 金鑰是否已設定為環境變數 GOOGLE_API_KEY。"

    prompt = format_data_for_prompt(stock_data)
    
    # List of models to try in order
    models_to_try = [
        'gemini-flash-latest',
        'gemini-pro-latest',
        'gemini-2.5-flash'
    ]
    
    last_error = None
    
    for model_name in models_to_try:
        try:
            print(f"🔄 正在嘗試使用模型: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            print(f"✅ 成功使用模型: {model_name}")
            return response.text
        except Exception as e:
            print(f"⚠️ 模型 {model_name} 失敗: {e}")
            last_error = e
            continue # Try the next model
            
    # If all models failed, return a comprehensive error message
    available_msg = ""
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        available_msg = f"\n\n系統偵測到的可用模型: {', '.join(all_models)}"
    except Exception as list_e:
        available_msg = f"\n\n無法列出模型 (API Key 可能無效或未啟用 API 服務): {list_e}"

    return (
        f"呼叫 Gemini API 失敗。所有備用模型均無法使用。\n"
        f"已嘗試模型: {', '.join(models_to_try)}\n"
        f"最後一個錯誤詳情: {last_error}" +
        available_msg
    )
