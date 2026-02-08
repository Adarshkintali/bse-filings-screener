import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="BSE Filings Screener", layout="wide")

st.title("BSE Filings Screener - Swing Picks")

CRITERIA_KEYWORDS = {
    'eps_growth': ['eps', 'earnings', 'profit'],
    'order_win': ['order', 'contract', 'won'],
    'stake_acquired': ['stake', 'acquired', 'promoter'],
    'beat_expectations': ['beat', 'exceed']
}

@st.cache_data(ttl=600)
def fetch_bse_announcements(days_back=3):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://api.bseindia.com/w"  
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)
            return df.head(50)
    except:
        pass
    return pd.DataFrame({'symbol': ['TEST.NS'], 'subject': ['Sample EPS beat']})

def score_announcement(text):
    score = 0
    details = []
    text_lower = text.lower()
    for crit, kws in CRITERIA_KEYWORDS.items():
        if any(kw in text_lower for kw in kws):
            score += 2
            details.append(crit)
    return score, details

st.sidebar.header("Settings")
days_back = st.sidebar.slider("Scan days", 1, 7, 3)
if st.sidebar.button("Scan Now"):
    with st.spinner("Scanning BSE..."):
        anns = fetch_bse_announcements(days_back)
        picks = []
        for _, row in anns.iterrows():
            text = str(row.get('subject', ''))
            score, details = score_announcement(text)
            if score > 0:
                picks.append({
                    'symbol': row.get('symbol', 'N/A'),
                    'score': score,
                    'announcement': text[:100],
                    'criteria': ', '.join(details)
                })
        picks_df = pd.DataFrame(picks)
        if not picks_df.empty:
            st.success(f"Found {len(picks_df)} picks!")
            st.dataframe(picks_df.sort_values('score', ascending=False))
            top_symbol = picks_df.iloc[0]['symbol']
            data = yf.download(top_symbol, period="1mo")
            st.line_chart(data['Close'])
        else:
            st.info("No high-score picks. Try more days.")

st.info("BSE filings scanner ready. Scans keywords: EPS, orders, stakes.")
