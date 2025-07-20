import yfinance as yf
from rich import print
from google import genai
from google.genai import types
import os
import requests

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

def call_gemini(ticker_symbol):
    client = genai.Client()
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )
    query = f'Why was there a drop in stock price for {ticker_symbol} in the past day? Please consult financial news sources, analyst reports, and SEC filings related to Netflix for the past day to figure out why it dropped.'
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

    return f"""{ticker} 

Price Details:
- Current Price: {current_price_str}
- Price at Open: {price_at_open_str}
- Previous Close: {price_at_close_str}
- Day's High: {price_at_high_str}

Gemini Summary:
{gemini_resp}

Regards,
Your Buy-The-Dip Bot
"""

def main():
    for ticker, price_data in screen():
        gemini_resp = call_gemini(ticker)
        send_notification(ticker, price_data, gemini_resp)

if __name__ == '__main__':
    main()
