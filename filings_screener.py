import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(layout="wide")
st.title("BSE/NSE 3-Day Filings Scanner")

CRITERIA = {
    "EPS": ["eps", "earnings", "beat"],
    "Stake": ["stake", "acquired"],
    "Order": ["order", "contract"]
}

def scrape_filings():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    filings = []
    total = 0
    
    # BSE
    try:
        resp = requests.get("https://www.bseindia.com/corporates/ann.aspx", headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("table tr")[:50]
        total += len(rows)
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 3:
                filings.append({
                    "symbol": cols[1].get_text(strip=True),
                    "title": cols[2].get_text(strip=True),
                    "date": cols[0].get_text(strip=True),
                    "exchange": "BSE"
                })
    except:
        pass
    
    # NSE
    try:
        resp = requests.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements", headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select(".table tr")[:30]
        total += len(rows)
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 2:
                filings.append({
                    "symbol": cols[0].get_text(strip=True),
                    "title": cols[1].get_text(strip=True),
                    "date": "Recent",
                    "exchange": "NSE"
                })
    except:
        pass
    
    df = pd.DataFrame(filings)
    return df, total

def score_title(title):
    lower = title.lower()
    score = 0
    trigger = ""
    for t, words in CRITERIA.items():
        for w in words:
            if w in lower:
                score += 3
                trigger = t
                break
    return score, trigger

col1, col2 = st.columns(2)
manual = col1.button("Scan Filings")
auto_start = col2.button("Auto 1hr")

if manual or auto_start:
    with st.spinner("Reading exchange filings..."):
        filings_df, total_read = scrape_filings()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Filings Read", total_read)
        col2.metric("3-Day Filings", len(filings_df))
        unique_stocks = len(filings_df['symbol'].unique()) if 'symbol' in filings_df.columns and not filings_df.empty else 0
        col3.metric("Stocks", unique_stocks)
        
        picks = []
        for _, row in filings_df.iterrows():
            if 'title' in row:
                score, trig = score_title(row['title'])
                if score > 1:
                    picks.append({
                        "Stock": row['symbol'],
                        "Trigger": trig,
                        "Score": score,
                        "Date": row['date'],
                        "Exchange": row['exchange']
                    })
        
        if picks:
            df_picks = pd.DataFrame(picks).sort_values("Score", ascending=False)
            st.success(f"Found {len(df_picks)} picks from {len(filings_df)} filings!")
            st.dataframe(df_picks)
        else:
            st.info(f"Read {total_read} filings - no strong matches")

st.caption("Scans BSE/NSE corporate filings last 3 days")
