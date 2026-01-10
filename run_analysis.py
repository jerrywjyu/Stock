import os
import toml
from FinMind_Stock import get_finmind_indicators
from gemini_analyzer import get_ai_analysis, configure_gemini

def main():
    """
    Reads the API key, fetches stock data, and runs AI analysis.
    """
    # 1. Read API key from secrets.toml and set it as an environment variable
    try:
        secrets = toml.load(".streamlit/secrets.toml")
        api_key = secrets.get("GOOGLE_API_KEY")
        if not api_key or api_key == "YOUR_API_KEY":
            print("❌ 請在 .streamlit/secrets.toml 檔案中設定您的 GOOGLE_API_KEY。")
            return
        os.environ["GOOGLE_API_KEY"] = api_key
        print("✅ API Key 已成功從 secrets.toml 讀取並設定為環境變數。")
    except FileNotFoundError:
        print("❌ 找不到 .streamlit/secrets.toml 檔案。")
        return
    except Exception as e:
        print(f"❌ 讀取 secrets.toml 檔案時發生錯誤：{e}")
        return

    # 2. Configure Gemini (now it will find the environment variable)
    if not configure_gemini():
        print("❌ Gemini AI 設定失敗。請再次檢查您的 API 金鑰。")
        return
    print("✅ Gemini AI 已成功設定。")

    # 3. Fetch stock data for a sample stock (e.g., 2330)
    stock_id = "2330"
    print(f"\n🔄 正在查詢股票 {stock_id} 的技術指標...")
    try:
        # We need to get the FinMind token from secrets as well for this to work
        finmind_token = secrets.get("FINMIND_TOKEN", "")
        if not finmind_token:
            print("⚠️ 未在 secrets.toml 中找到 FINMIND_TOKEN，將在沒有 token 的情況下繼續。")
        
        # We also need the stock name
        from twse_stock_list import fetch_twse_stock_list
        df_stocks = fetch_twse_stock_list()
        stock_name = df_stocks[df_stocks['證券代號'] == stock_id].iloc[0]['證券名稱']

        stock_data = get_finmind_indicators(stock_id, stock_name=stock_name, token=finmind_token)
        
        if not isinstance(stock_data, dict):
            print(f"❌ 查詢股票數據失敗：{stock_data}")
            return
            
        print(f"✅ 成功獲取 {stock_name} 的數據。")
    except Exception as e:
        print(f"❌ 查詢股票 {stock_id} 數據時發生錯誤：{e}")
        return

    # 4. Get AI analysis
    print("\n🤖 正在呼叫 Gemini 進行分析...")
    analysis_result = get_ai_analysis(stock_data)

    # 5. Print the result
    print("\n--- 💎 Gemini 分析結果 ---")
    print(analysis_result)
    print("--------------------------")

if __name__ == "__main__":
    main()
