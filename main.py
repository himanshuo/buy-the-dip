import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from rich import print

SAFE_STOCK_LIST = ['NFLX', 'QTUM', 'AAPL', 'GOOG', 'BRK/B', 'COST', 'WMT']

def fetch_stock_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        return {
            'current_price': ticker.fast_info.last_price,
            'price_at_open': ticker.fast_info.open,
            'price_at_close': ticker.fast_info.previous_close,
            'price_at_high': ticker.fast_info.day_high,
        }
    except Exception as e:
        print(f"An error occurred while fetching data for {ticker_symbol}: {e}")
        if 'Too Many Requests' in str(e):
            raise e
        return None

def alert(data):
    threshold = .03
    for key, value in data.items():
        if key == 'current_price':
            pass
        else:
            if value*(1-threshold) > data['current_price']:
                return True
    return False

def screen():
    alerts = []
    for stock in SAFE_STOCK_LIST[:1]:
        data = fetch_stock_data(SAFE_STOCK_LIST[0])
        if alert(data):
            alerts.append((stock, data))
    return alerts


def main():
    print(screen())


if __name__ == '__main__':
    main()