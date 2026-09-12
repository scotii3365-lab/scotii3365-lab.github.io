import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

# --- KR Data Logic ---
def get_kr_fundamental_data(ticker, current_price):
    url = f"https://m.stock.naver.com/api/stock/{ticker}/finance/annual"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code != 200:
            return None
        data = res.json()
        finance_info = data.get('financeInfo')
        if not finance_info:
            return None
        
        tr_list = finance_info.get('trTitleList', [])
        # 확정 실적(isConsensus == 'N') 중 가장 최근과 그 직전 연도
        actual_keys = [tr['key'] for tr in tr_list if tr.get('isConsensus') == 'N']
        if not actual_keys:
            actual_keys = [tr['key'] for tr in tr_list]
        
        if len(actual_keys) >= 2:
            curr_key = actual_keys[-1]
            prev_key = actual_keys[-2]
        elif len(actual_keys) == 1:
            curr_key = actual_keys[0]
            prev_key = None
        else:
            return None

        row_map = {r['title']: r.get('columns', {}) for r in finance_info.get('rowList', [])}

        def parse_val(title, key):
            if not key or title not in row_map:
                return 0.0
            col_info = row_map[title].get(key)
            if not col_info:
                return 0.0
            val_str = col_info.get('value', '-')
            if val_str in ['-', '', None]:
                return 0.0
            try:
                return float(str(val_str).replace(',', ''))
            except (ValueError, TypeError):
                return 0.0

        roe = parse_val('ROE', curr_key)
        margin = parse_val('영업이익률', curr_key)
        debt_ratio = parse_val('부채비율', curr_key)
        per = parse_val('PER', curr_key)
        eps = parse_val('EPS', curr_key)
        prev_eps = parse_val('EPS', prev_key) if prev_key else 0.0

        eps_growth = ((eps - prev_eps) / abs(prev_eps) * 100) if prev_eps != 0 else 0.0

        return {
            'Symbol': ticker,
            'ROE': roe,
            'Margin': margin,
            'DebtRatio': debt_ratio,
            'PER': per,
            'EPSGrowth': eps_growth,
            'Price': current_price
        }
    except Exception as e:
        print(f"Failed to fetch KR {ticker}: {e}")
        return None

# --- US Data Logic ---
def get_us_fundamental_data(ticker):
    yf_ticker = ticker.replace('.', '-')
    try:
        time.sleep(0.1) # 과도한 요청 방지
        stock = yf.Ticker(yf_ticker)
        info = stock.info
        if not info or not isinstance(info, dict):
            print(f"Failed to fetch {ticker}: Empty info from yfinance")
            return None
        roe = info.get('returnOnEquity', 0)
        margin = info.get('operatingMargins', 0)
        debt_to_equity = info.get('debtToEquity', 0)
        eps_growth = info.get('earningsGrowth', 0)
        per = info.get('trailingPE') or info.get('forwardPE', 0)
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
    except Exception as e:
        print(f"Failed to fetch {ticker}: {e}")
        return None

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

    # 2. US Stocks (NASDAQ 300 + NYSE 300)
    print("미국 주요 종목 데이터 수집 중 (나스닥 300 + 뉴욕 300)...")
    try:
        df_nasdaq = fdr.StockListing('NASDAQ').head(300)
        df_nasdaq['MarketInfo'] = 'US_NASDAQ'
        
        df_nyse = fdr.StockListing('NYSE').head(300)
        df_nyse['MarketInfo'] = 'US_NYSE'
        
        us_all = pd.concat([df_nasdaq, df_nyse]).drop_duplicates(subset=['Symbol'])
        us_symbols = us_all['Symbol'].tolist()
        us_market_map = {row['Symbol']: row['MarketInfo'] for _, row in us_all.iterrows()}
    except Exception as e:
        print(f"미국 리스트 확보 실패 ({e}), S&P 500으로 대체합니다.")
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
            if count % 50 == 0:
                print(f"미국 종목 진행 상황: {count}/{len(us_symbols)}...")

    # Save to JSON
    df = pd.DataFrame(all_results)
    df.to_json('stocks_all.json', orient='records', force_ascii=False)
    print(f"총 {len(df)}개 종목 수집 완료! (stocks_all.json 저장됨)")

if __name__ == "__main__":
    main()
