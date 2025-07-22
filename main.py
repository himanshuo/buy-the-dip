import yfinance as yf
from rich import print
from google import genai
from google.genai import types
import os
import requests
import math
from stock_list import TOP_ETFS, SP100

SAFE_STOCK_LIST = TOP_ETFS + SP100

def fetch_stock_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        return {
            'current_price': ticker.fast_info.last_price,
            'price_at_open': ticker.fast_info.open,
            'price_at_close': ticker.fast_info.previous_close,
            'price_at_high': ticker.fast_info.day_high,
            'name': ticker.info['longName'],
        }
    except Exception as e:
        print(f"An error occurred while fetching data for {ticker_symbol}: {e}")
        if 'Too Many Requests' in str(e):
            raise e
        return None

def alert(data, market_change):
    threshold = .03 + (-1.0*market_change)
    current_price = data['current_price']
    max_comparable_price = max(data['price_at_open'], data['price_at_close'], data['price_at_high'])
    return max_comparable_price*(1-threshold) > current_price

def screen():
    market = fetch_stock_data('VOO')
    market_change = (market['current_price'] - market['price_at_open']) / market['price_at_open']
    for stock in SAFE_STOCK_LIST:
        data = fetch_stock_data(stock)
        if alert(data, market_change):
            yield stock, data

def call_gemini(ticker_symbol, ticker_name):
    client = genai.Client()
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )
    query = f'Why was there a drop in stock price for {ticker_symbol} in the past day? Please consult financial news sources, analyst reports, earnings reports, and SEC filings related to {ticker_name} for today and yesterday to figure out why it dropped.'
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config=config,
    )

    print(response.text)
    return response.text

def send_notification(ticker, price_data, gemini_resp):
  	return requests.post(
  		"https://api.mailgun.net/v3/sandboxae39eddfee26494d9dc97ed6713b531b.mailgun.org/messages",
  		auth=("api", os.environ['MAILGUN_SEND_KEY']),
  		data={"from": "Mailgun Sandbox <postmaster@sandboxae39eddfee26494d9dc97ed6713b531b.mailgun.org>",
			"to": "Himanshu Ojha <himanshuo@gmail.com>",
  			"subject": f"[Buy-The-Dip] {ticker}",
  			"text": format_email_contents(ticker, price_data, gemini_resp)})

def change_price_str(current_price, other_price):
    price_diff_percentage =  (current_price - other_price) / other_price * 100
    return f"${other_price:.2f} (current price is {price_diff_percentage:.2f}%)"

def format_email_contents(ticker, price_data, gemini_resp):
    current_price_str = f"${price_data['current_price']:.2f}"
    price_at_open_str = change_price_str(price_data['current_price'], price_data['price_at_open'])
    price_at_close_str = change_price_str(price_data['current_price'], price_data['price_at_close'])
    price_at_high_str = change_price_str(price_data['current_price'], price_data['price_at_high'])
    buy_amount = math.floor(100/price_data['current_price'])
    return f"""{ticker} 

Price Details:
- Current Price: {current_price_str}
- Price at Open: {price_at_open_str}
- Previous Close: {price_at_close_str}
- Day's High: {price_at_high_str}

Buy {buy_amount} shares at {current_price_str}

Gemini Summary:
{gemini_resp}

Regards,
Your Buy-The-Dip Bot
"""

def main():
    for ticker, stock_data in screen():
        gemini_resp = call_gemini(ticker, stock_data['name'])
        send_notification(ticker, stock_data, gemini_resp)

if __name__ == '__main__':
    main()
