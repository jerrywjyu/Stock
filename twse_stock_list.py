
import pandas as pd
import requests
import os
from io import StringIO

def fetch_twse_stock_list(cache_file='twse_stock_list.csv'):
    # 若本地有快取，直接讀取
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, dtype=str)
        return df
    # 下載台灣證交所上市公司清單（含產業類別）
    url = 'https://isin.twse.com.tw/isin/C_public.jsp?strMode=2'
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res.encoding = 'big5'
    tables = pd.read_html(StringIO(res.text))
    df = tables[0]
    df.columns = df.iloc[0]
    df = df[1:]
    df = df.rename(columns={df.columns[0]: '證券代號及名稱'})
    df = df[df['證券代號及名稱'].str.contains('\d{4}', na=False)]
    df['證券代號'] = df['證券代號及名稱'].str.extract(r'(\d{4})')
    df['證券名稱'] = df['證券代號及名稱'].str.replace(r'^\d{4}\s+', '', regex=True)
    df = df[['證券代號', '證券名稱', '產業別']]
    df.to_csv(cache_file, index=False, encoding='utf-8-sig')
    return df

if __name__ == '__main__':
    df = fetch_twse_stock_list()
    print(df.head())
