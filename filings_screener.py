import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from sec_api import QueryApi, ExtractorApi
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page config
st.set_page_config(page_title="SEC Filings Screener", layout="wide")

st.title("🔍 SEC Filings Screener")
st.markdown("**Screen US stocks by latest 10-K/10-Q filings, financials & sentiment**")

# Sidebar
st.sidebar.header("⚙️ Filters")
ticker_input = st.sidebar.text_input("Tickers (comma sep)", value="AAPL,MSFT,GOOGL")
date_range = st.sidebar.date_input("Filing Date Range", value=(datetime.now()-timedelta(days=365), datetime.now()))
form_types = st.sidebar.multiselect("Form Types", ["10-K", "10-Q", "8-K"], default=["10-K", "10-Q"])
keywords = st.sidebar.text_input("Keywords", "growth,risk,revenue")

if st.sidebar.button("🚀 Screen Filings"):
    with st.spinner("Fetching SEC data..."):
        # SEC API setup (use your free key from sec-api.io)
        api_key = st.secrets.get("SEC_API_KEY", "demo")  # Add your key to Streamlit secrets
        query_api = QueryApi(api_key=api_key)
        
        tickers = [t.strip().upper() for t in ticker_input.split(",")]
        results = []
        
        for ticker in tickers:
            query = {
                "query": f'ticker:{ticker} AND formType:({",".join(form_types)}) AND filedAt:[{date_range[0].strftime("%Y-%m-%d")} TO {date_range[1].strftime("%Y-%m-%d")}]',
                "from": "0",
                "size": "5",
                "sort": [{"filedAt": {"order": "desc"}}]
            }
            
            filings = query_api.get_filings(query)
            
            for filing in filings.get('filings', []):
                # Get financial data via yfinance
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period="1mo")
                
                results.append({
                    'Ticker': ticker,
                    'Company': info.get('longName', ticker),
                    'Form': filing['formType'],
                    'Filed Date': filing['filedAt'],
                    'Accession #': filing['accessionNo'],
                    'Market Cap': info.get('marketCap', 'N/A'),
                    'P/E Ratio': info.get('trailingPE', 'N/A'),
                    'Revenue Growth': info.get('revenueGrowth', 'N/A'),
                    'Filing URL': f"https://www.sec.gov/Archives/edgar/data/{filing['cik']}/{filing['accessionNo'].replace('-','')}/{filing['primaryDocument']}"
                })
        
        if results:
            df = pd.DataFrame(results)
            
            # Main dashboard
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Filings Summary")
                st.dataframe(df, use_container_width=True)
                
                # Sentiment analysis placeholder
                st.subheader("📈 Key Metrics")
                col_a, col_b, col_c = st.columns(3)
                with col_a: st.metric("Avg P/E", df['P/E Ratio'].mean())
                with col_b: st.metric("Total Filings", len(df))
                with col_c: st.metric("Latest Filing", df['Filed Date'].max())
            
            with col2:
                st.subheader("📈 Price Performance")
                fig = px.line(pd.DataFrame(hist.reset_index(), columns=['Date', ticker]), 
                             x='Date', y=ticker, title=f"{ticker} 1M Price")
                st.plotly_chart(fig, use_container_width=True)
            
            # Download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download CSV", csv, "sec_filings.csv", "text/csv")
            
        else:
            st.warning("No filings found. Try broader date range or different tickers.")

# Footer
st.markdown("---")
st.markdown("*Data: SEC EDGAR via sec-api.io [web:9], Yahoo Finance [web:10]. Built with Streamlit.*")
