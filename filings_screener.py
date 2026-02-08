import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import PyPDF2
import io
import re
import time
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Filings Screener Pro - PDF + Screener")

st.title("🔥 NSE/BSE PDF Filings Screener (Max 3 Days + Screener EPS)")

@st.cache_data(ttl=1800)
def fetch_bse_filings_max(pages=5):  # Max free ~125 entries
    filings = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    base_url = "https://www.bseindia.com"
    for page in range(1, pages+1):
        url = f"https://www.bseindia.com/corporates/ann.aspx?expandable=6&page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'lxml')
            rows = soup.select("table.tablebg tr")[1:26]
            for row in rows:
                cols = [td.text.strip() for td in row.find_all('td')]
                if len(cols) >= 4:
                    symbol = re.sub(r's+', '', cols[1]).upper() + '.NS'
                    title = cols[2].lower()
                    date_str = cols[3]
                    # Get PDF URL
                    pdf_link = row.find('a', href=re.compile(r'pdf|PDF'))
                    pdf_url = base_url + pdf_link['href'] if pdf_link else ''
                    filings.append({'symbol': symbol, 'title': title, 'date': date_str, 'exchange': 'BSE', 'pdf_url': pdf_url})
        except Exception as e:
            st.error(f"BSE page {page}: {e}")
        time.sleep(2)
    return pd.DataFrame(filings)

@st.cache_data(ttl=1800)
def fetch_nse_filings_max():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    filings = []
    # NSE announcements page + actions for max
    urls = [
        "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
        "https://www.nseindia.com/companies-listing/corporate-filings-actions"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'lxml')
            rows = soup.select("tbody tr")[:30]  # Max visible
            for row in rows:
                cols = [td.text.strip() for td in row.find_all('td')]
                if len(cols) >= 3:
                    symbol = cols[0].upper() + '.NS'
                    title = ' '.join(cols[1:]).lower()
                    date_str = cols[-1]
                    pdf_link = row.find('a', href=re.compile(r'pdf'))
                    pdf_url = pdf_link['href'] if pdf_link else ''
                    filings.append({'symbol': symbol, 'title': title, 'date': date_str, 'exchange': 'NSE', 'pdf_url': pdf_url})
        except:
            pass
        time.sleep(1)
    return pd.DataFrame(filings)

def extract_pdf_text(pdf_url):
    if not pdf_url:
        return ""
    try:
        resp = requests.get(pdf_url, timeout=20, stream=True)
        reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
        text = ""
        for page in reader.pages[:5]:  # First 5 pages
            text += page.extract_text().lower() or ""
        return text
    except:
        return ""

@st.cache_data(ttl=3600)
def get_screener_eps(symbol):
    """Extract QoQ EPS % from Screener.in"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://www.screener.in/company/{symbol.replace('.NS', '/')}/"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'lxml')
        # Parse quarterly profit growth (QoQ proxy)
        qoq_match = re.search(r'Quarterlys+profitsgrowths+YoYs+(%)?s*</th>s*<td[^>]*>([d.-]+)', resp.text, re.I)
        eps_growth = float(qoq_match.group(1)) if qoq_match else 0
        return eps_growth
    except:
        return 0

CRITERIA = {
    'EPS_Beat': ['eps', 'earning', 'result', 'beat', 'exceed', 'surpass'],
    'EPS_Growth': ['eps growth', 'profit up', 'revenue growth', 'qoq increase'],
    'Stake_Acquired': ['stake acquire', 'promoter holding increase', 'shareholding pattern'],
    'Famous_Investor': ['ambani', 'jhunjhunwala', 'damani', 'rakesh'],
    'Order_Win': ['order receive', 'contract win', 'rs d+ cr', 'deal']
}

def score_filing(title, pdf_text):
    text = (title + " " + pdf_text).lower()
    score = 0
    trigger = []
    for cat, kws in CRITERIA.items():
        matches = sum(text.count(kw) for kw in kws)
        if matches:
            score += matches * 2
            trigger.append(cat)
    return score, ', '.join(set(trigger))

def get_stock_metrics(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        price = info.get('currentPrice', 0)
        hist = ticker.history(period="3mo")
        fall_pct = 0
        if not hist.empty:
            low_3m = hist['Low'].min()
            fall_pct = max(0, (low_3m - price) / price * 100)  # % from low
        eps_growth = get_screener_eps(symbol)
        return price, fall_pct, eps_growth
    except:
        return 0, 0, 0

# RUN SCAN
if st.button("🚀 Full PDF Scan + Screener EPS") or st.session_state.get('scan_active'):
    st.session_state.scan_active = True
    with st.spinner("Max scraping BSE/NSE + PDF read + Screener EPS... (5-10min)"):
        bse_df = fetch_bse_filings_max(5)
        nse_df = fetch_nse_filings_max()
        all_filings = pd.concat([bse_df, nse_df]).drop_duplicates('pdf_url')
        
        # 3-day filter (approx regex)
        cutoff_pattern = '|'.join([f'Feb-0{datetime.now().day-1:02d}', 'Feb-07', 'Feb-08', 'Today', 'Yesterday'])
        recent_filings = all_filings[all_filings['date'].str.contains(cutoff_pattern, na=False, regex=True)]
        
        picks = []
        total_read = len(all_filings)
        recent_count = len(recent_filings)
        pdf_analyzed = 0
        
        for _, filing in recent_filings.iterrows():
            pdf_text = extract_pdf_text(filing['pdf_url'])
            if pdf_text:
                pdf_analyzed += 1
            
            score, trigger = score_filing(filing['title'], pdf_text)
            if score >= 2:
                price, fall_pct, eps_growth = get_stock_metrics(filing['symbol'])
                if price > 0 and eps_growth > 20:  # High EPS filter
                    upside = min(100, (score * 8) + (eps_growth * 0.3) + fall_pct)  # Enhanced formula
                    picks.append({
                        'Stock': filing['symbol'],
                        'Trigger': trigger,
                        'EPS Growth QoQ %': f"{eps_growth:.0f}%",
                        'Current Price': f"₹{price:.0f}",
                        'Expected Upside %': f"{upside:.0f}%",
                        'Filing Date': filing['date'],
                        'Exchange': filing['exchange'],
                        'Score': score
                    })
        
        picks_df = pd.DataFrame(picks).sort_values('Score', ascending=False)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Filings", total_read)
        col2.metric("3-Day Filings", recent_count)
        col3.metric("PDFs Analyzed", pdf_analyzed)
        col4.metric("Picks (EPS>20%)", len(picks_df))
        
        if not picks_df.empty:
            st.success(f"🎯 {len(picks_df)} High-Quality Picks!")
            st.dataframe(picks_df.head(15), use_container_width=True)
            
            # Chart
            if len(picks_df) > 0:
                top = picks_df.iloc[0]
                ticker = yf.Ticker(top['Stock'])
                hist = ticker.history(period="6mo")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Close'))
                fig.add_hline(y=top['Current Price'][:-1], line_dash="dash", annotation_text="Current")
                fig.update_layout(title=f"{top['Stock']} - Beaten Down + {top['EPS Growth QoQ %']} EPS")
                st.plotly_chart(fig)
        else:
            st.info(f"Full scan: {total_read} filings, {pdf_analyzed} PDFs, {recent_count} recent - No EPS>20% matches (try weekdays).")

st.sidebar.title("Settings")
st.sidebar.slider("BSE Pages", 3, 10, 5)
if st.sidebar.button("Auto-Scan"):
    st.rerun()
st.sidebar.caption("PDF full-text + Screener.in EPS QoQ. Max free scrape.")
