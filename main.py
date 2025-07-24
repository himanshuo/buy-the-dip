import yfinance as yf
from rich import print
from google import genai
from google.genai import types
import os
import requests
import math
from stock_list import TOP_ETFS, SP100
import numpy as np

SAFE_STOCK_LIST = TOP_ETFS + SP100

def fetch_stock_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        name = ticker.info['longName'] if ticker.info.__contains__('longName') else ticker.info['shortName']
        slope = get_slope(ticker)
        return {
            'current_price': ticker.fast_info.last_price,
            'price_at_open': ticker.fast_info.open,
            'price_at_close': ticker.fast_info.previous_close,
            'price_at_high': ticker.fast_info.day_high,
            'yesterday_low': ticker.history(period='2d').Low.iloc[0],
            '2y_slope': slope,
            'is_etf': ticker_symbol in TOP_ETFS,
            'name': name,
        }
    except Exception as e:
        print(f"An error occurred while fetching data for {ticker_symbol}: {e}")
        if 'Too Many Requests' in str(e):
            raise e
        return None

def get_slope(ticker):
    ylist = ticker.history(period='2y', interval='1mo').Close
    xlist = [i for i in range(0, len(ylist))]

    line = np.polyfit(xlist, ylist, deg=1)
    slope = line[0]
    return slope

def alert(data, market_change):
    if rapid_growth(data):
        print(f"Skipping {data['name']} because of recent rapid growth")
        return False
    if downwards_slope(data):
        print(f"Skipping {data['name']} because of 2-year downwards slope")
        return False

    return current_price_dipped_relative_to_market(data, market_change)

def current_price_dipped_relative_to_market(data, market_change):
    threshold = .01 if data['is_etf'] else .03
    threshold_with_mkt_chng = threshold + (-1.0 * market_change)
    current_price = data['current_price']
    max_comparable_price = max(data['price_at_open'], data['price_at_close'], data['price_at_high'])
    return max_comparable_price * (1 - threshold_with_mkt_chng) > current_price

def rapid_growth(data):
    current_price = data['current_price']
    yesterday_low = data['yesterday_low']
    return yesterday_low * 1.07 < current_price

def downwards_slope(data):
    slope = data['2y_slope']
    return slope < 0

def screen():
    market = fetch_stock_data('VOO')
    market_change = (market['current_price'] - market['price_at_open']) / market['price_at_open']
    for stock in SAFE_STOCK_LIST:
        data = fetch_stock_data(stock)
        if alert(data, market_change):
            yield stock, data

def ask_why_drop(ticker_symbol, ticker_name):
    query = (f'Why was there a drop in stock price for {ticker_symbol} in the past day? Please consult financial news '
             f'sources, analyst reports, earnings reports, and SEC filings related to {ticker_name} for today and '
             f'yesterday to figure out why it dropped.')
    return call_gemini(query)

def ask_if_actually_drop(why_drop):
    query = f"I asked gemini why there was a price drop for the stock and it provided me with the below response. Can you read it, think about the response, and tell me if the response actually thinks there was a drop? Yes means there was a drop. At the end of your response, just say yes or no.  \n\n {why_drop}"
    is_drop = call_gemini(query)
    return is_yes_result(is_drop)

def ask_long_term(why_drop):
    query = f"I asked gemini why there was a price drop for the stock and it provided me with the below response. Can you read it, think about the response, and tell me if the reason for the drop is long term, medium or short term? At the end of your response, just say long, medium, or short.  \n\n {why_drop}"
    is_long_term = call_gemini(query)
    return is_long_term_result(is_long_term)

def is_yes_result(gemini_response):
    relevant_response = gemini_response[-4:]
    relevant_response = strip_fluff(relevant_response)
    return relevant_response == 'yes'

def is_long_term_result(gemini_response):
    relevant_response = gemini_response[-5:]
    relevant_response = strip_fluff(relevant_response)
    return relevant_response == 'long'

def strip_fluff(resp):
    resp = resp.lower()
    resp = resp.strip()
    resp = resp.strip('.')
    return resp

def call_gemini(query):
    client = genai.Client()
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )
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
        why_drop = ask_why_drop(ticker, stock_data['name'])
        is_drop = ask_if_actually_drop(why_drop)
        if not is_drop:
            continue
        is_long_term = ask_long_term(why_drop)
        if is_long_term:
            continue
        send_notification(ticker, stock_data, why_drop)
if __name__ == '__main__':
    main()
