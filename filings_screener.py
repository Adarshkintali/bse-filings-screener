import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(layout="wide")
st.title("Exchange Filings Scanner - Last 3 Days")

CRITERIA = {
    "EPS_Beat": ["eps", "earnings", "beat"],
    "Stake": ["stake", "acquired"],
    "Order": ["order", "contract"],
    "Growth": ["growth", "profit"]
}

def scrape_filings():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    filings = []
    total_read = 0
    
    try:
        resp = requests.get("https://www.bseindia.com/corporates/ann.aspx", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tr")[1:60]
        total_read += len(rows)
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 2:
                date = cols[0].text.strip()
                if "Today" in date or "Yesterday" in date:
                    filings.append({
                        "symbol": cols[1].text.strip(),
                        "title": cols[2].text.strip(),
                        "date": date,
                        "exchange": "BSE"
                    })
    except:
        pass
    
    try:
        resp = requests.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements", headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select(".table tr")[1:40]
        total_read += len(rows)
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 1:
                filings.append({
                    "symbol": cols[0].text.strip(),
                    "title": cols[1].text.strip(),
                    "date": "recent",
                    "exchange": "NSE"
                })
    except:
        pass
    
    return pd.DataFrame(filings), total_read

def score_filing(title):
    title_lower = title.lower()
    triggers = []
    score = 0
    for trigger, kws in CRITERIA.items():
        for kw in kws:
            if kw in title_lower:
                score += 3
                triggers.append(trigger)
                break
    return score, ", ".join(triggers)

# Controls
col1, col2, col3 = st.columns(3)
manual_scan = col1.button("Manual Scan")
if col2.button("Auto 1hr"):
    st.session_state.auto = True
if col3.button("Pause"):
    st.session_state.auto = False

if manual_scan:
    with st.spinner("Scanning 3-day filings..."):
        filings_df, total_read = scrape_filings()
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Read", total_read)
        col_b.metric("3-Day Filings", len(filings_df))
        col_c.metric("Matches", filings_df['symbol'].nunique())
        
        results = []
        for _, row in filings_df.iterrows():
            score, trigger = score_filing(row['title'])
            if score > 1:
                try:
                    data = yf.download(row['symbol'] + '.NS', period="3mo", progress=False)
                    price = data['Close'][-1]
                    upside = score * 5
                    results.append({
                        'Stock': row['symbol'],
                        'Trigger': trigger,
                        'Price': f"Rs {price:.0f}",
                        'Upside': f"{upside}%",
                        'Date': row['date'],
                        'Exchange': row['exchange']
                    })
                except:
                    pass
        
        if results:
            df = pd.DataFrame(results).sort_values('Upside', ascending=False)
            st.success(f"Found {len(df)} picks from {len(filings_df)} 3-day filings!")
            st.dataframe(df)
        else:
            st.info(f"Read {total_read} filings, {len(filings_df)} recent - no high scores")

st.caption("Last 3 days BSE/NSE filings | Auto every hour")
