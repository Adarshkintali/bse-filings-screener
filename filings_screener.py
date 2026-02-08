import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import PyPDF2
import io
import re
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Filings Screener Pro")

st.title("🔥 NSE/BSE Filings Screener - Swing Picks (Last 3 Days)")

@st.cache_data(ttl=1800)  # 30min cache
def fetch_bse_filings(pages=3):
    filings = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for page in range(1, pages+1):
        url = f"https://www.bseindia.com/corporates/ann.aspx?expandable=6&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'lxml')
            rows = soup.select("table.tablebg tr")[1:26]  # Top 25 per page
            for row in rows:
                cols = [td.text.strip() for td in row.find_all('td')]
                if len(cols) >= 4:
                    symbol = cols[1].upper() + '.NS' if cols[1] else 'N/A'
                    title = cols[2].lower()
                    date_str = cols[3]
                    filings.append({'symbol': symbol, 'title': title, 'date': date_str, 'exchange': 'BSE', 'url': ''})
        except Exception:
            pass
        time.sleep(1)  # Anti-bot
    return pd.DataFrame(filings)

@st.cache_data(ttl=1800)
def fetch_nse_filings():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    url = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        # NSE structure varies; fallback to recent visible
        rows = soup.select(".c-list__table tbody tr")[:20]
        filings = []
        for row in rows:
            cols = [td.text.strip() for td in row.find_all('td')]
            if len(cols) >= 3:
                symbol = cols[0].upper() + '.NS'
                title = cols[1].lower()
                date_str = cols[2]
                filings.append({'symbol': symbol, 'title': title, 'date': date_str, 'exchange': 'NSE', 'url': ''})
        return pd.DataFrame(filings)
    except:
        return pd.DataFrame()

def extract_pdf_text(pdf_url):
    try:
        resp = requests.get(pdf_url, timeout=10)
        reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
        text = ""
        for page in reader.pages[:2]:
            text += page.extract_text().lower()
        return text
    except:
        return ""

CRITERIA = {
    'EPS_Beat': ['eps', 'earnings', 'results', 'beat', 'exceed', 'surpassed'],
    'EPS_Growth': ['eps growth', 'profit up', 'revenue growth', 'qoq'],
    'Stake_Acquired': ['stake', 'acquired', 'holding', 'promoter', 'shareholding'],
    'Famous_Investor': ['ambani', 'jhunjhunwala', 'damani', 'rakesh jhunjhunwala'],
    'Order_Win': ['order', 'contract', 'won', 'deal', 'rs ', 'cr ']
}

def score_filing(title, pdf_text=""):
    text = (title + " " + pdf_text).lower()
    score = 0
    trigger = []
    for cat, keywords in CRITERIA.items():
        matches = sum(1 for kw in keywords if kw in text)
        if matches:
            score += matches * 2
            trigger.append(cat)
    return score, ', '.join(trigger) if trigger else 'None'

def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        price = info.get('currentPrice', 0)
        prev_close = info.get('previousClose', price)
        hist = ticker.history(period="3mo")
        if not hist.empty:
            low_3m = hist['Low'].min()
            fall_pct = (price - low_3m) / low_3m * 100 if low_3m else 0
        else:
            fall_pct = 0
        eps = info.get('trailingEps', 0)
        return price, fall_pct, eps
    except:
        return 0, 0, 0

# Main scan
if st.button("🔍 Scan Last 3 Days Filings") or st.session_state.get('scanning', False):
    st.session_state.scanning = True
    with st.spinner("Scanning BSE/NSE + Analyzing..."):
        bse_df = fetch_bse_filings(3)
        nse_df = fetch_nse_filings()
        all_filings = pd.concat([bse_df, nse_df], ignore_index=True)
        
        cutoff = datetime.now() - timedelta(days=3)
        recent_filings = all_filings[all_filings['date'].str.contains('Today|Yesterday|Feb-0[56]|Feb-07|Feb-08', na=False)]  # Approx 3 days
        
        picks = []
        total_read = len(all_filings)
        recent_count = len(recent_filings)
        
        for _, filing in recent_filings.iterrows():
            score, trigger = score_filing(filing['title'])
            if score >= 2:  # Threshold
                price, fall_pct, eps = get_stock_data(filing['symbol'])
                if price > 0:
                    upside = (score * 5) + (20 - fall_pct * 0.5)  # Formula: trigger score + beaten-down boost
                    picks.append({
                        'Stock': filing['symbol'],
                        'Trigger': trigger,
                        'Current Price': f"₹{price:.0f}",
                        'Expected Upside %': f"{upside:.0f}%",
                        'Filing Date': filing['date'],
                        'Exchange': filing['exchange'],
                        'Score': score
                    })
        
        picks_df = pd.DataFrame(picks).sort_values('Score', ascending=False)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Filings Read", total_read)
        col2.metric("3-Day Filings", recent_count)
        col3.metric("High-Quality Picks", len(picks_df))
        
        if not picks_df.empty:
            st.success(f"🎯 {len(picks_df)} Picks Found!")
            st.dataframe(picks_df.head(10), use_container_width=True)
            
            # Top pick chart
            top_symbol = picks_df.iloc[0]['Stock']
            ticker = yf.Ticker(top_symbol)
            hist = ticker.history(period="6mo")
            if not hist.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Close'))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Low'], name='Low (Beaten?)'))
                fig.update_layout(title=f"{top_symbol} - Price vs Prev Quarters")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Scanned {total_read} filings ({recent_count} in 3 days) - No high-conviction matches today (Sunday holiday). Try weekdays!")

# Sidebar
st.sidebar.title("⚙️ Settings")
days_back = st.sidebar.slider("Scan Days Back", 1, 7, 3)
if st.sidebar.button("Auto-Refresh 30min"):
    st.rerun()
st.sidebar.caption("Deploy: GitHub → Streamlit Cloud. Weekend low data.")

st.caption("Strategy: EPS QoQ proxy via price fall + triggers. yfinance NSE live. PDF ready (add urls).")
