import requests
import os
import webbrowser
import base64
import pandas as pd
from rich import print
from datetime import datetime, timedelta


class SchwabClient:
    """
    A client for interacting with the Schwab API.
    """
    def __init__(self):
        """
        Initializes the SchwabClient.
        """
        self.api_key = os.environ.get('SCHWAB_API_KEY')
        self.api_secret = os.environ.get('SCHWAB_API_SECRET')
        self.access_token = None
        self._refresh_access_token()
        self.account_num_hash = self._get_account_num_hash()

    def _refresh_access_token(self):
        refresh_token_value = self._get_saved_refresh_token()

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_value,
        }
        headers = {
            "Authorization": f'Basic {base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()}',
            "Content-Type": "application/x-www-form-urlencoded",
        }

        refresh_token_response = requests.post(
            url="https://api.schwabapi.com/v1/oauth/token",
            headers=headers,
            data=payload,
        )
        if refresh_token_response.status_code == 200:
            print("Retrieved new tokens successfully using refresh token.")
        else:
            print(
                f"Error refreshing access token: {refresh_token_response.text}. Trying oauth from the start."
            )
            self._do_oauth_from_start()
            return None

        refresh_token_dict = refresh_token_response.json()

        print(refresh_token_dict)

        print("Token dict refreshed.")
        self._save_refresh_token(refresh_token_dict["refresh_token"])
        self.access_token = refresh_token_dict['access_token']
        return None

    def _get_saved_refresh_token(self):
        file_path = 'schwab_refresh_token.txt'
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                print(f"Retrieved refresh token: {content}")
                return content
        except FileNotFoundError:
            print(f"Error: The file at {file_path} was not found.")
        except Exception as e:
            print(f"An error occurred: {e}")
        return None

    def _save_refresh_token(self, refresh_token):
        file_path = 'schwab_refresh_token.txt'
        try:
            with open(file_path, 'w') as file:
                file.write(refresh_token)
        except Exception as e:
            print(f"An error occurred: {e}")
        return None

    def _do_oauth_from_start(self):
        tokens_dict = self._get_access_token()
        self._save_refresh_token(tokens_dict['refresh_token'])
        self.access_token = tokens_dict['access_token']

    def _create_auth_request(self, returned_url, app_key, app_secret):
        response_code = f"{returned_url[returned_url.index('code=') + 5: returned_url.index('%40')]}@"

        credentials = f"{app_key}:{app_secret}"
        base64_credentials = base64.b64encode(credentials.encode("utf-8")).decode(
            "utf-8"
        )

        headers = {
            "Authorization": f"Basic {base64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        payload = {
            "grant_type": "authorization_code",
            "code": response_code,
            "redirect_uri": "https://127.0.0.1",
        }

        return headers, payload

    def _retrieve_tokens(self, headers, payload) -> dict:
        init_token_response = requests.post(
            url="https://api.schwabapi.com/v1/oauth/token",
            headers=headers,
            data=payload,
        )

        init_tokens_dict = init_token_response.json()

        return init_tokens_dict

    def _get_access_token(self):
        """
        Retrieves an access token from Schwab.

        """
        auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={self.api_key}&redirect_uri=https://127.0.0.1"
        webbrowser.open(auth_url)

        print("Paste Returned URL:")
        returned_url = input()

        init_token_headers, init_token_payload = self._create_auth_request(
            returned_url, self.api_key, self.api_secret
        )

        init_tokens_dict = self._retrieve_tokens(
            headers=init_token_headers, payload=init_token_payload
        )

        print(init_tokens_dict)

        return init_tokens_dict

    def _get_account_num_hash(self):
        response = requests.get(
            "https://api.schwabapi.com/trader/v1/accounts/accountNumbers",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        print(response, response.text)
        response_frame = pd.json_normalize(response.json())
        print(f"Account Number Hash: {response_frame['hashValue'].iloc[0]}")
        return response_frame["hashValue"].iloc[0]

    def view_positions(self):
        response = requests.get(
            f"https://api.schwabapi.com/trader/v1/accounts/{self.account_num_hash}?fields=positions",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        print(response, response.text)
        return response.json()

    def view_open_orders(self):
        open_orders = []
        working_orders = self.make_view_open_orders_request("WORKING")
        pending_activation_orders = self.make_view_open_orders_request("PENDING_ACTIVATION")
        open_orders.extend(working_orders)
        open_orders.extend(pending_activation_orders)
        return open_orders

    def make_view_open_orders_request(self, status):
        old_time = "2025-07-01T00:00:00.000Z"
        new_time_obj = datetime.now() + timedelta(hours=24)
        new_time = new_time_obj.strftime('%Y-%m-%dT%H:%M:%S') + f'.{new_time_obj.microsecond // 1000:03d}Z'
        url_prefix = f"https://api.schwabapi.com/trader/v1/accounts/{self.account_num_hash}/orders?fromEnteredTime={old_time}&toEnteredTime={new_time}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = requests.get(url_prefix + f"&status={status}", headers=headers)
        print(response, response.text)
        return response.json()

    def place_buy_order(self, ticker, quantity, limit_price):
        """
        Places a BUY LIMIT order through the Schwab API.

        Args:
            ticker: The stock symbol to buy.
            quantity: The number of shares to buy.
            limit_price: The limit price.

        Returns:
            The JSON response from the API.
        """
        if quantity == 0:
            print(f"Skipping BUY for {ticker} because quantity is 0.")
            return
        endpoint = f"https://api.schwabapi.com/trader/v1/accounts/{self.account_num_hash}/orders"
        cancel_time = (datetime.now() + timedelta(days=60)).isoformat(timespec='milliseconds') + 'Z'


        body_limit_order = {
            "session": "NORMAL",
            "duration": "GOOD_TILL_CANCEL",
            "orderType": "LIMIT",
            "cancelTime": cancel_time,
            "complexOrderStrategyType": "NONE",
            "quantity": quantity,
            "price": limit_price,
            "activationPrice": 0,
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "orderLegType": "EQUITY",
                    "instruction": "BUY",
                    "quantity": quantity,
                    "quantityType": "SHARES",
                    "instrument": {
                        "symbol": ticker.upper(),
                        "assetType": "EQUITY"
                    },
                    "positionEffect": "AUTOMATIC",
                    "legId": "1"
                }
            ]
        }
        print(f"POST {endpoint} \n {body_limit_order}")
        try:
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.access_token}"
                },
                json=body_limit_order)
            response.raise_for_status()  # Raise an exception for bad status codes
            print(f"Buy Limit order placed successfully. status code = {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while placing the buy limit order: {e}")
            if e.response:
                print(f"Response content: {e.response.text}")

if __name__ == '__main__':
    client = SchwabClient()
    # client.view_positions()
    # client.view_open_orders()
    # client.place_trade("buy", "IQ", 2, 1.5)
    # client.place_trade("sell", "IQ", 2, 2.1)


