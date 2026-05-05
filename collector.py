import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor

# --- KR Data Logic ---
def get_kr_fundamental_data(ticker, current_price):
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
        
        # 실시간 PER 계산: 현재가 / 최신 연간 EPS
        eps = clean_val(target_df.loc['EPS(원)'].iloc[curr_idx])
        per = (current_price / eps) if eps > 0 else 0
        
        prev_eps = clean_val(target_df.loc['EPS(원)'].iloc[prev_idx])
        eps_growth = ((eps - prev_eps) / prev_eps * 100) if prev_eps > 0 else 0
        return {
            'Symbol': ticker,
            'ROE': roe,
            'Margin': margin,
            'DebtRatio': debt_ratio,
            'PER': per,
            'EPSGrowth': eps_growth,
            'Price': current_price
        }
    except: return None

# --- US Data Logic ---
def get_us_fundamental_data(ticker):
    try:
        time.sleep(0.1) # 과도한 요청 방지
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

    # 1. KR Stocks (KOSPI 500 + KOSDAQ 500)
    print("한국 주요 종목 데이터 수집 중 (코스피 500 + 코스닥 500)...")
    kr_kospi = fdr.StockListing('KOSPI').sort_values(by='Marcap', ascending=False).head(500)
    kr_kosdaq = fdr.StockListing('KOSDAQ').sort_values(by='Marcap', ascending=False).head(500)
    kr_all = pd.concat([kr_kospi, kr_kosdaq])
    
    kr_info = {row['Code']: {'Name': row['Name'], 'Market': row['Market'], 'Close': row['Close']} for _, row in kr_all.iterrows()}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_kr_fundamental_data, code, kr_info[code]['Close']): code for code in kr_info}
        for future in futures:
            res = future.result()
            if res:
                code = res['Symbol']
                res['Name'] = kr_info[code]['Name']
                res['Market'] = 'KR_' + kr_info[code]['Market']
                all_results.append(res)

    # 2. US Stocks (NASDAQ 1000 + NYSE 1000)
    print("미국 주요 종목 데이터 수집 중 (나스닥 1000 + 뉴욕 1000)...")
    try:
        df_nasdaq = fdr.StockListing('NASDAQ').head(1000)
        df_nasdaq['MarketInfo'] = 'US_NASDAQ'
        
        df_nyse = fdr.StockListing('NYSE').head(1000)
        df_nyse['MarketInfo'] = 'US_NYSE'
        
        us_all = pd.concat([df_nasdaq, df_nyse]).drop_duplicates(subset=['Symbol'])
        us_symbols = us_all['Symbol'].tolist()
        us_market_map = {row['Symbol']: row['MarketInfo'] for _, row in us_all.iterrows()}
    except:
        print("미국 리스트 확보 실패, S&P 500으로 대체합니다.")
        df_sp500 = fdr.StockListing('S&P500')
        us_symbols = df_sp500['Symbol'].tolist()
        us_market_map = {s: 'US_SP500' for s in us_symbols}
    
    print(f"미국 종목 {len(us_symbols)}개 중 데이터 수집 중...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_us_fundamental_data, symbol): symbol for symbol in us_symbols}
        count = 0
        for future in futures:
            res = future.result()
            count += 1
            if res:
                symbol = res['Symbol']
                res['Market'] = us_market_map.get(symbol, 'US_UNKNOWN')
                all_results.append(res)
            if count % 100 == 0:
                print(f"미국 종목 진행 상황: {count}/{len(us_symbols)}...")

    # Save to JSON
    df = pd.DataFrame(all_results)
    df.to_json('stocks_all.json', orient='records', force_ascii=False)
    print(f"총 {len(df)}개 종목 수집 완료! (stocks_all.json 저장됨)")

if __name__ == "__main__":
    main()
