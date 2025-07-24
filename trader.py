from schwab_client import SchwabClient
import math
from main import fetch_stock_data

def ensure_sell_limit_orders_for_all():
    client = SchwabClient()
    current_positions = client.view_positions()['securitiesAccount']['positions']
    open_orders = client.view_open_orders()
    tickers_with_open_orders = [order['orderLegCollection'][0]['instrument']['symbol'] for order in open_orders]
    for current_position in current_positions:
        if current_position['instrument']['symbol'] in tickers_with_open_orders:
            continue
        basis_price = current_position['averagePrice']
        current_price = fetch_stock_data(current_position['instrument']['symbol'])['current_price']
        base_price_for_high_selling = max(basis_price, current_price)
        high_price_to_sell = round(base_price_for_high_selling * 1.04, 2)
        qty = math.floor(current_position['longQuantity'])
        client.place_sell_order(current_position['instrument']['symbol'], qty, high_price_to_sell)

def setup_buy_orders():
    tickers_to_buy = []

    client = SchwabClient()
    for ticker in tickers_to_buy:
        limit_price = round(fetch_stock_data(ticker)['current_price'], 2)
        quantity = 1
        client.place_buy_order(ticker, quantity, limit_price)


def main():
    # ensure_sell_limit_orders_for_all()
    # setup_buy_orders()
    client = SchwabClient()
    client.place_sell_order('IAU', 1, 66)

    # client = SchwabClient()
    # client.place_sell_order('HUYA', 1, 4, 3.6)
    # client.view_positions()
    # client.view_open_orders()
    # client.place_trade("buy", "IQ", 2, 1.5)
    # client.place_trade("sell", "IQ", 2, 2.1)

if __name__ == '__main__':
    main()


