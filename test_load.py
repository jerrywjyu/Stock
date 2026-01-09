from data_storage import load_analysis_history
import traceback

try:
    print("Attempting to load analysis history...")
    df = load_analysis_history()
    print("Load successful. DataFrame content:")
    print(df)
    if df.empty:
        print("DataFrame is empty after loading.")
except Exception as e:
    print(f"An error occurred while loading history: {e}")
    print(traceback.format_exc())
