import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import requests

st.set_page_config(page_title="BSE Filings Screener", layout="wide")

st.title("BSE Filings Screener - Swing Trading Picks")

CRITERIA_KEYWORDS = {
    'beat_expectations': ['beat', 'exceed', 'above'],
    'eps_growth': ['eps', 'earnings growth'],
    'stake_acquired': ['stake acquired', 'promoter holding'],
    'famous_invest': ['invested', 'jhunjhunwala', 'ambani'],
    'order_win': ['order win', 'contract', 'rs crore']
}

@st.cache_data(ttl=1800)
def get_bse_data():
    symbols = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ITC.NS']
    announcements = []
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            news = ticker.news[:3]
            for item in news:
                title = item['title']
                announcements.append({'symbol': sym, 'title': title, 'date': item['providerPublishTime']})
        except:
            pass
    return pd.DataFrame(announcements)

def score_title(title):
    title_lower = title.lower()
    score = 0
    details = []
    for crit, keywords in CRITERIA_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                score += 2
                details.append(crit)
                break
    return score, details

st.sidebar.header("Scan Settings")
days_back = st.sidebar.slider("Lookback days", 1, 30, 7)
if st.sidebar.button("Full BSE Scan"):
    with st.spinner('Scanning major stocks...'):
        data = get_bse_data()
        if not data.empty:
            picks = []
            for _, row in data.iterrows():
                score, details = score_title(row['title'])
                if score > 0:
                    picks.append({
                        'Symbol': row['symbol'],
                        'Score': score,
                        'Announcement': row['title'][:80] + '...',
                        'Criteria': ', '.join(details)
                    })
            picks_df = pd.DataFrame(picks)
            if not picks_df.empty:
                st.success(f"Found {len(picks_df)} high-quality picks!")
                st.dataframe(picks_df.sort_values('Score', ascending=False))
                
                top_pick = picks_df.iloc[0]['Symbol']
                chart_data = yf.download(top_pick, period="1mo")
                st.subheader(f"{top_pick} Price Chart")
                st.line_chart(chart_data['Close'])
            else:
                st.info("No matching criteria today. Adjust keywords.")
        else:
            st.warning("No data. Market holiday?")

st.info("""
Scans top NSE stocks news for:
- EPS beats/growth
- Stake acquisitions  
- Famous investor buys
- Order wins

Customize CRITERIA_KEYWORDS in code.
""")
