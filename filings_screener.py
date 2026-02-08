# filings_screener.py
# NSE/BSE Filings Screener for Swing Trading Picks
# Run with: streamlit run filings_screener.py
# pip install streamlit bse yfinance pandas numpy requests beautifulsoup4 schedule python-dotenv

import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import requests
from bs4 import BeautifulSoup
from bse import BSE
import schedule
import time
from datetime import datetime, timedelta
import os
from typing import List, Dict

st.set_page_config(page_title="Filings Screener", layout="wide")

st.title("📋 NSE/BSE Filings Screener for High-Quality Swing Picks")

# Custom criteria keywords for high-quality picks
CRITERIA_KEYWORDS = {
    'beat_expectations': ['beat', 'exceed', 'above expectation', 'surpassed'],
    'eps_growth': ['eps growth', 'earnings per share', 'eps increase', '% eps'],
    'beaten_down': ['52 week low', 'down %', 'fallen sharply', 'oversold'],
    'stake_acquired': ['acquired stake', 'controlling stake', 'promoter stake', 'increased stake'],
    'famous_invest': ['invested', 'rakesh jhunjhunwala', 'radhakrishnan damani', 'warren buffett', 'billionaire'],
    'order_win': ['order win', 'contract win', 'large order', 'rs crore order']
}

@st.cache_data(ttl=300)  # 5 min cache for announcements
def fetch_bse_announcements(days_back=7):
    """Fetch recent BSE announcements using bse lib"""
    try:
        with BSE() as bse:
            from_date = (datetime.now() - timedelta(days=days_back)).strftime('%d-%m-%Y')
            to_date = datetime.now().strftime('%d-%m-%Y')
            anns = bse.allAnnouncements(fromDate=from_date, toDate=to_date)
            df = pd.DataFrame(anns)
            if not df.empty:
                df['date'] = pd.to_datetime(df['datetime'], format='%d-%b-%Y %H:%M')
                df = df.sort_values('date', ascending=False)
            return df
    except Exception as e:
        st.error(f"BSE fetch error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_nse_announcements():
    """Scrape NSE recent announcements (simplified, NSE hard to scrape)"""
    url = "https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date=01-01-2026&to_date=08-02-2026"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data.get('data', []))
            return df
    except:
        pass
    # Fallback RSS-like scrape
    rss_url = "https://www.nseindia.com/rss/corporate.rss"  # Hypothetical, check actual
    return pd.DataFrame()

def score_announcement(text: str, symbol: str) -> Dict[str, float]:
    """Score announcement text against criteria"""
    text_lower = text.lower()
    score = 0.0
    details = {}
    for crit, kws in CRITERIA_KEYWORDS.items():
        matches = sum(1 for kw in kws if kw in text_lower)
        if matches > 0:
            score += matches * 2  # Weight matches
            details[crit] = matches
    # Bonus for beaten down: check price vs 52w low
    try:
        data = yf.download(symbol, period="1y", progress=False)
        if not data.empty:
            beaten_factor = (data['Close'].max() - data['Close'][-1]) / data['Close'].max()
            if beaten_factor > 0.3:  # Down >30% from peak
                score += 3
                details['beaten_down_price'] = beaten_factor
    except:
        pass
    return {'score': score, 'details': details}

def screen_picks(anns_df: pd.DataFrame) -> pd.DataFrame:
    """Screen for high quality picks"""
    picks = []
    for _, row in anns_df.iterrows():
        text = str(row.get('subject', '') + ' ' + row.get('summary', ''))
        symbol = row.get('scripcode', row.get('symbol', ''))
        score_dict = score_announcement(text, symbol)
        if score_dict['score'] > 2:  # Threshold
            picks.append({
                'symbol': symbol,
                'date': row.get('date'),
                'announcement': row.get('subject', ''),
                'score': score_dict['score'],
                'criteria': score_dict['details']
            })
    return pd.DataFrame(picks).sort_values('score', ascending=False)

# Streamlit UI
st.sidebar.header("Scan Settings")
days_back = st.sidebar.slider("Scan last days", 1, 30, 7)
refresh = st.sidebar.button("🔄 Refresh Filings")

if refresh or st.sidebar.button("🚀 Continuous Scan"):
    with st.spinner("Fetching filings..."):
        bse_anns = fetch_bse_announcements(days_back)
        nse_anns = fetch_nse_announcements()
        all_anns = pd.concat([bse_anns, nse_anns], ignore_index=True) if not nse_anns.empty else bse_anns

    if not all_anns.empty:
        picks_df = screen_picks(all_anns)
        if not picks_df.empty:
            st.success(f"Found {len(picks_df)} high-quality picks!")

            # Top Picks Table
            st.subheader("🏆 Top Swing Trade Picks")
            display_df = picks_df[['symbol', 'score', 'date', 'announcement']].copy()
            display_df['criteria'] = picks_df['criteria'].apply(lambda x: ', '.join(x.keys()))
            st.dataframe(display_df.head(10), use_container_width=True)

            # Detailed View
            selected = st.selectbox("View details", picks_df['symbol'].tolist())
            if selected:
                pick = picks_df[picks_df['symbol'] == selected].iloc[0]
                st.json(pick)

            # Price Chart for top pick
            if not picks_df.empty:
                top_symbol = picks_df.iloc[0]['symbol']
                data = yf.download(top_symbol + '.NS' if '.NS' not in top_symbol else top_symbol, period="3mo")
                if not data.empty:
                    st.subheader(f"📈 {top_symbol} Chart")
                    st.line_chart(data['Close'])
        else:
            st.info("No high-quality picks matching criteria today. Adjust scan days.")
    else:
        st.warning("No announcements fetched. BSE works well; NSE scraping tricky due to protections. Focus on BSE.") [web:59]

# Continuous scheduler (runs in background)
def job():
    st.rerun()

if st.sidebar.checkbox("Enable Auto-Refresh (every 30min)"):
    schedule.every(30).minutes.do(job)
    schedule.run_pending()
    time.sleep(1)

st.info("""
🔧 **Notes**:
- Powered by BSE API for reliable announcements [web:64]
- Screens for your criteria: EPS beats, stake buys, order wins etc.
- Beaten-down check uses yfinance price data.
- NSE scraping challenging (Akamai bot protection) - BSE primary [web:59][web:60]
- Customize `CRITERIA_KEYWORDS` or `score_announcement` for your rules.
- For live deploy: Use Streamlit Cloud + scheduler.

Share specific strategy tweaks!
""")
st.info("""
Notes:
- Powered by BSE API for announcements
- Screens EPS beats, stake buys, order wins
- Customize CRITERIA_KEYWORDS dict
- Beaten-down: >30% from peak
Share your strategy rules!
""")
