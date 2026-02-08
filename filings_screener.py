import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

st.set_page_config(layout="wide")
st.title("BSE/NSE Filings Scanner - Last 3 Days")

CRITERIA = {
    'EPS_Beat': ['eps', 'earnings', 'results', 'beat'],
    'EPS_Growth': ['growth', 'profit up'],
    'Stake_Acquired': ['stake', 'acquired'],
    'Order_Win': ['order', 'contract', 'crore']
}

def date_to_days(date_str):
    try:
        if 'Yesterday' in date_str:
            return 1
        if 'Today' in date_str:
            return 0
        return 99  # Old
    except:
        return 99

@st.cache_data(ttl=3600)
def scrape_last_3_days():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    filings, total_read = [], 0
    
    # BSE Last 3 days
    try:
        resp = requests.get("https://www.bseindia.com/corporates/ann.aspx", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        bse_rows = soup.select('table tr')[1:100]
        total_read += len(bse_rows)
        
        for row in bse_rows:
            cols = row.find_all('td')
            if len(cols) > 2:
                date_str = cols[0].text.strip()
                days_old = date_to_days(date_str)
                if days_old <= 3:  # Last 3 days only
                    filings.append({
                        'symbol': cols[1].text.strip(),
                        'title': cols[2].text.strip(),
                        'date': date_str,
                        'exchange': 'BSE'
                    })
    except:
        pass
    
    # NSE Last 3 days
    try:
        resp = requests.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        nse_rows = soup.select('.table tr')[1:50]
        total_read += len(nse_rows)
        
        for row in nse_rows:
            cols = row.find_all('td')
            if len(cols) > 1:
                date_str = cols[0].text.strip() if len(cols) > 0 else 'recent'
                days_old = date_to_days(date_str)
                if days_old <= 3:
                    filings.append({
                        'symbol': cols[0].text.strip(),
                        'title': cols[1].text.strip(),
                        'date': date_str,
                        'exchange': 'NSE'
                    })
    except:
        pass
    
    return pd.DataFrame(filings), total_read

def analyze_filing(title, symbol):
    title_lower = title.lower()
    triggers, score = [], 0
    
    for trigger, kws in CRITERIA.items():
        for kw in kws:
            if kw in title_lower:
                score += 3
                triggers.append(trigger)
                break
    
    try:
        data = yf.download(symbol + '.NS', period="6mo", progress=False)
        curr = data['Close'][-1]
        peak = data['Close'].max()
        fall_pct = (peak - curr) / peak * 100
        upside = max(25, score * 4 + fall_pct * 0.5)
        return {
            'triggers': ', '.join(triggers),
            'score': score,
            'curr_price': round(curr, 2),
            'upside_pct': round(upside, 1),
            'fall_pct': round(fall_pct, 1)
        }
    except:
        return {'triggers': ', '.join(triggers), 'score': score, 'curr_price': 0, 'upside_pct': 0, 'fall_pct': 0}

# Controls
if 'auto' not in st.session_state:
    st.session_state.auto = False
    st.session_state.last_scan = 0

cols = st.columns(3)
manual = cols[0].button("🔄 Scan Now")
cols[1].button("▶️ Auto 1hr", use_container_width=True)
cols[2].button("⏹️ Stop", use_container_width=True)

if st.session_state.auto and time.time() - st.session_state.last_scan > 3600:
    manual = True
    st.session_state.last_scan = time.time()

if manual:
    with st.spinner("Scanning last 3 days filings..."):
        filings_df, total_read = scrape_last_3_days()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total
