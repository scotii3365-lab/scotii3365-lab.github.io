import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor

# --- KR Data Logic ---
def get_kr_fundamental_data(ticker):
    url = f"https://finance.naver.com/item/main.nhn?code={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        df_list = pd.read_html(io.StringIO(res.text))
        target_df = None
        for df in df_list:
            if any('주요재무정보' in str(col) for col in df.columns):
                target_df = df
                break
        if target_df is None: return None
        target_df.index = target_df.iloc[:, 0]
        curr_idx, prev_idx = 3, 2
        def clean_val(val):
            if pd.isna(val) or val == '-': return 0
            return float(str(val).replace(',', ''))
        roe = clean_val(target_df.loc['ROE(지배주주)'].iloc[curr_idx])
        margin = clean_val(target_df.loc['영업이익률'].iloc[curr_idx])
        debt_ratio = clean_val(target_df.loc['부채비율'].iloc[curr_idx])
        per = clean_val(target_df.loc['PER(배)'].iloc[curr_idx])
        eps = clean_val(target_df.loc['EPS(원)'].iloc[curr_idx])
        prev_eps = clean_val(target_df.loc['EPS(원)'].iloc[prev_idx])
        eps_growth = ((eps - prev_eps) / prev_eps * 100) if prev_eps > 0 else 0
        return {
            'Symbol': ticker,
            'ROE': roe,
            'Margin': margin,
            'DebtRatio': debt_ratio,
            'PER': per,
            'EPSGrowth': eps_growth,
            'Price': 0 # Placeholder for KR
        }
    except: return None

# --- US Data Logic ---
def get_us_fundamental_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        roe = info.get('returnOnEquity', 0)
        margin = info.get('operatingMargins', 0)
        debt_to_equity = info.get('debtToEquity', 0)
        eps_growth = info.get('earningsGrowth', 0)
        per = info.get('forwardPE') or info.get('trailingPE', 0)
        price = info.get('currentPrice', 0)
        return {
            'Symbol': ticker,
            'Name': info.get('shortName', ticker),
            'ROE': roe * 100 if roe else 0,
            'Margin': margin * 100 if margin else 0,
            'DebtRatio': debt_to_equity if debt_to_equity else 0,
            'EPSGrowth': eps_growth * 100 if eps_growth else 0,
            'PER': per if per else 0,
            'Price': price
        }
    except: return None

def main():
    print("=== 통합 데이터 수집 시작 ===")
    all_results = []

    # 1. KR Stocks (KOSPI 200 + KOSDAQ 200)
    print("한국 주식 데이터 수집 중...")
    kr_kospi = fdr.StockListing('KOSPI').sort_values(by='Marcap', ascending=False).head(200)
    kr_kosdaq = fdr.StockListing('KOSDAQ').sort_values(by='Marcap', ascending=False).head(200)
    kr_all = pd.concat([kr_kospi, kr_kosdaq])
    
    kr_codes = kr_all['Code'].tolist()
    kr_info = {row['Code']: {'Name': row['Name'], 'Market': row['Market']} for _, row in kr_all.iterrows()}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_kr_fundamental_data, code): code for code in kr_codes}
        for future in futures:
            res = future.result()
            if res:
                code = res['Symbol']
                res['Name'] = kr_info[code]['Name']
                res['Market'] = 'KR_' + kr_info[code]['Market']
                all_results.append(res)

    # 2. US Stocks (S&P 500)
    print("미국 주식 데이터 수집 중...")
    us_sp500 = fdr.StockListing('S&P500')
    us_symbols = us_sp500['Symbol'].tolist()
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(get_us_fundamental_data, symbol): symbol for symbol in us_symbols}
        for future in futures:
            res = future.result()
            if res:
                res['Market'] = 'US_SP500'
                all_results.append(res)

    # Save to JSON
    df = pd.DataFrame(all_results)
    df.to_json('stocks_all.json', orient='records', force_ascii=False)
    print(f"총 {len(df)}개 종목 수집 완료! (stocks_all.json 저장됨)")

if __name__ == "__main__":
    main()
