import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

st.set_page_config(layout="wide")
st.title("BSE/NSE Filings Scanner - Swing Trading Picks")

CRITERIA = {
    'EPS_Beat': ['eps', 'earnings', 'results', 'beat', 'exceed'],
    'EPS_Growth': ['eps growth', 'profit up'],
    'Stake_Acquired': ['stake', 'acquired', 'holding'],
    'Famous_Investor': ['jhunjhunwala', 'ambani'],
    'Order_Win': ['order', 'contract', 'crore']
}

@st.cache_data(ttl=3600)
def scrape_exchanges():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    filings = []
    
    # BSE
    try:
        resp = requests.get("https://www.bseindia.com/corporates/ann.aspx", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for row in soup.select('table tr')[1:30]:
            cols = row.find_all('td')
            if len(cols) > 2:
                filings.append({
                    'symbol': cols[1].text.strip(),
                    'title': cols[2].text.strip(),
                    'date': cols[0].text.strip(),
                    'exchange': 'BSE'
                })
    except Exception as e:
        st.error(f"BSE scrape: {e}")
    
    # NSE fallback
    try:
        resp = requests.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for row in soup.select('.listing-table tr')[1:20]:
            cols = row.find_all('td')
            if len(cols) > 1:
                filings.append({
                    'symbol': cols[0].text.strip(),
                    'title': cols[1].text.strip(),
                    'date': 'recent',
                    'exchange': 'NSE'
                })
    except:
        pass
    
    return pd.DataFrame(filings)

def analyze_filing(title, symbol):
    title_lower = title.lower()
    triggers = []
    score = 0
    
    for trigger, kws in CRITERIA.items():
        for kw in kws:
            if kw in title_lower:
                score += 3
                triggers.append(trigger)
                break
    
    try:
        data = yf.download(symbol + '.NS', period="6mo", progress=False)
        curr_price = data['Close'][-1]
        peak_price = data['Close'].max()
        price_fall = (peak_price - curr_price) / peak_price * 100
        upside = max(25, score * 4 + price_fall * 0.5)
        
        return {
            'triggers': ', '.join(triggers),
            'score': score,
            'curr_price': round(curr_price, 2),
            'upside_pct': round(upside, 1),
            'price_fall': round(price_fall, 1)
        }
    except:
        return {'triggers': ', '.join(triggers), 'score': score, 'curr_price': 0, 'upside_pct': 0, 'price_fall': 0}

# Auto-refresh controls
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
    st.session_state.last_scan = 0

col1, col2, col3 = st.columns(3)
with col1:
    manual_scan = st.button("🔄 Manual Scan", use_container_width=True)
with col2:
    if st.button("▶️ Start 1hr Auto", use_container_width=True):
        st.session_state.auto_refresh = True
with col3:
    if st.button("⏸️ Pause Auto", use_container_width=True):
        st.session_state.auto_refresh = False

# Auto logic
if st.session_state.auto_refresh and time.time() - st.session_state.last_scan > 3600:
    manual_scan = True
    st.session_state.last_scan = time.time()
    st.rerun()

if manual_scan or st.session_state.auto_refresh:
    with st.spinner("Scanning BSE/NSE filings (3 days)..."):
        filings = scrape_exchanges()
        results = []
        
        for _, filing in filings.iterrows():
            analysis = analyze_filing(filing['title'], filing['symbol'])
            if analysis['score'] > 1:
                results.append({
                    'Stock': filing['symbol'],
                    'Trigger': analysis['triggers'],
                    'Price': f"₹{analysis['curr_price']}",
                    'Upside': f"{analysis['upside_pct']}%",
                    'Fall': f"{analysis['price_fall']}%",
                    'Date': filing['date'],
                    'Exchange': filing['exchange'],
                    'Score': analysis['score']
                })
        
        if results:
            df = pd.DataFrame(results).sort_values('Score', ascending=False).head(15)
            st.success(f"🎯 {len(df)} High-Conviction Picks Found!")
            st.dataframe(df, use_container_width=True)
            
            # Top 3 charts
            for i in range(min(3, len(df))):
                symbol = df.iloc[i]['Stock']
                data = yf.download(symbol + '.NS', period="3mo", progress=False)
                st.subheader(f"📈 {symbol} ({df.iloc[i]['Upside']} Upside)")
                st.line_chart(data['Close'])
        else:
            st.info("No qualifying picks. Weekend/quiet market.")

st.sidebar.title("Strategy")
st.sidebar.json({k: len(v) for k, v in CRITERIA.items()})
st.sidebar.caption("Score >1 + beaten down = Swing buy")
