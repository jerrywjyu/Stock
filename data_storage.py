import pandas as pd
import os
from datetime import datetime

# --- Constants ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_FILE = os.path.join(SCRIPT_DIR, 'analysis_history.csv')
LOG_FILE = os.path.join(SCRIPT_DIR, 'debug_log.txt')
HEADER = ['Date', 'StockID', 'StockName', 'Analysis']

# --- Helper Functions ---
def log_message(message: str):
    """Appends a message to the debug log file."""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] {message}\n")

# --- Function Definitions ---
def save_analysis_to_csv(stock_id: str, stock_name: str, analysis: str):
    """
    Appends AI analysis results to a CSV file using pandas for robust handling.
    """
    log_message("--- Attempting to save analysis ---")
    log_message(f"Stock ID: {stock_id}, Stock Name: {stock_name}")
    log_message(f"Analysis Text Length: {len(analysis)} characters")
    
    try:
        new_entry = pd.DataFrame([{
            'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'StockID': stock_id,
            'StockName': stock_name,
            'Analysis': analysis
        }])

        file_exists = os.path.exists(ANALYSIS_FILE)
        log_message(f"Analysis file '{ANALYSIS_FILE}' exists: {file_exists}")

        # No try/except here to ensure we see the error if it happens
        new_entry.to_csv(
            ANALYSIS_FILE,
            mode='a',
            header=not file_exists,
            index=False,
            encoding='utf-8-sig'
        )

        log_message("Successfully wrote to CSV using pandas.")
        return True, f"Successfully saved analysis to {ANALYSIS_FILE}"

    except Exception as e:
        log_message(f"ERROR in save_analysis_to_csv: {e}")
        import traceback
        log_message(traceback.format_exc())
        return False, f"Failed to save analysis: {e}"

def load_analysis_history(limit: int = 100):
    """
    Loads analysis history from the CSV file using pandas.
    """
    log_message("--- Attempting to load analysis history ---")
    try:
        if not os.path.exists(ANALYSIS_FILE):
            log_message("Analysis file does not exist. Returning empty DataFrame.")
            return pd.DataFrame(columns=HEADER)
        
        if os.path.getsize(ANALYSIS_FILE) == 0:
            log_message("Analysis file is empty. Returning empty DataFrame.")
            return pd.DataFrame(columns=HEADER)

        log_message("Reading CSV file with pandas.")
        df = pd.read_csv(ANALYSIS_FILE, encoding='utf-8-sig', on_bad_lines='warn')

        if not all(col in df.columns for col in HEADER):
            log_message(f"ERROR: Malformed CSV. Expected columns: {HEADER}, but got: {list(df.columns)}")
            raise ValueError("CSV file is malformed.")

        if df.empty:
            log_message("DataFrame is empty after loading. Returning empty DataFrame.")
            return pd.DataFrame(columns=HEADER)

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df.dropna(subset=['Date'], inplace=True)
        df = df.sort_values(by='Date', ascending=False)
        
        log_message(f"Successfully loaded and parsed {len(df)} records.")
        return df.head(limit).copy()

    except Exception as e:
        log_message(f"ERROR in load_analysis_history: {e}")
        import traceback
        log_message(traceback.format_exc())
        return pd.DataFrame(columns=HEADER)