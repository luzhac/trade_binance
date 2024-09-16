import inspect
import math
import time
from datetime import datetime, timedelta
from turtle import pd

from binance.error import ClientError
from binance.spot import Spot
from trade_binance.utils import get_env_variable, GmailAPIWrapper, write_log,get_config



class BinanceAPIWrapper:
    def __init__(self):
        if get_config('api_key') and get_config('api_secret'):
            self.client = Spot(api_key=get_env_variable('api_key'), api_secret=get_env_variable('api_secret'))
        else:
            raise EnvironmentError(f"Config variable api_key or api_secret is missing")
        if get_config('environment') == 'development':
            self.client = Spot(api_key=get_env_variable('api_key'), api_secret=get_env_variable('api_secret'))
        else:
            self.client = Spot(api_key='', api_secret='')
        if get_config('quote_asset'):
            self.quote_asset = get_config('quote_asset')
        else:
            raise EnvironmentError(f"Config variable quote_asset is missing")
        self.margin_symbol_list = {}
        self.spot_symbol_list = {}
        self.price_filter = {}
        self.lot_size = {}
        self.huilv = {}

        self.gmailAPIWrapper = GmailAPIWrapper()
        self.set_filter()

    def set_filter(self):
        """
        Sets the filters for trading pairs based on the exchange information.

        This method retrieves the exchange information from the Binance API and sets the lot size and price filters
        for trading pairs that match the quote asset and are currently trading. The filters are stored in the
        `self.lot_size` and `self.price_fiter` dictionaries.

        The method performs the following steps:
        1. Calls the `my_exchange_info` method to get the exchange information.
        2. Iterates over the symbols in the exchange information.
        3. For each symbol, checks if the quote asset matches `self.quote_asset` and if the symbol is trading.
        4. If the symbol matches, sets the lot size and price filters based on the symbol's filters.

        Raises:
            Exception: If there is an error while setting the filters.

        Example:
            self.set_filter()
        """
        response = self.my_exchange_info()
        for row in response['symbols']:
            row_symbol = row['symbol']
            row_base_asset = row_symbol['baseAsset']
            row_quote_asset = row_symbol['quoteAsset']
            filter_out = False
            if row_quote_asset and get_config('symbol_list'):
                if row_base_asset not in [base_asset + get_config('quote_asset') for base_asset in
                                          get_config('symbol_list')]:
                    filter_out = True
            if not filter_out:
                if row_quote_asset == self.quote_asset and row['status'] == 'TRADING':
                    if not self.price_filter[row_quote_asset]:
                        self.price_filter[row_quote_asset] = 0.1 ** int(row['quotePrecision'])
                    for row_filter in row['filters']:
                        if row_filter['filterType'] == 'LOT_SIZE':
                            try:
                                self.lot_size[row_base_asset] = float(row_filter['minQty'])
                            except Exception as e:
                                self.lot_size[row_base_asset] = None
                                write_log('set_filter', row_base_asset, row_filter['minQty'], e)
                        if row_filter['filterType'] == 'PRICE_FILTER':
                            try:
                                self.price_filter[row_base_asset] = float(row_filter['minPrice'])
                            except Exception as e:
                                self.price_filter[row_base_asset] = None
                                write_log('set_filter', row_base_asset, row_filter['minPrice'], e)

    def handle_connection_error(self, e):
        write_log(f"ConnectionError: {e}")
        time.sleep(1)  # Wait longer before retrying
        return False

    def handle_index_error(self, e):
        write_log(f"handle_index_error: {e}")
        self.gmailAPIWrapper.send_email('index error.', '413')
        time.sleep(1)  # Wait longer before retrying
        return True

    def handle_timeout_error(self, e):
        write_log(f"TimeoutError: {e}")
        time.sleep(1)  # Wait a bit before retrying
        return False

    def handle_value_error(self, e):
        write_log(f"ValueError: {e}")
        return False

    def handle_client_error(self, error: ClientError):
        write_log(f"ClientError: {error.error_message}")
        if error.error_message == 'Exceeding the maximum transferable limit.':
            return True
        elif error.error_message == 'Balance is not enough':
            return True
        elif error.error_message == 'Margin account are not allowed to trade this trading pair.':
            return True
        elif error.error_message == 'This isolated margin pair is disabled. Please activate it.':
            return True
        elif error.error_message == 'Illegal characters found in a parameter.':
            return True
        elif error.error_message == 'Too many requests; current request has limited.':
            self.gmailAPIWrapper.send_email('enable Too many requests; current request has limited.', '')
            return True
        elif error.error_message == 'You cannot disable this isolated margin pair, as there are still assets or debts of this pair.':
            return True
        elif error.error_message == 'Transfer out amount exceeds max amount.':
            return True
        elif error.error_message == 'Balance is not enough':
            return True
        elif error.error_message == 'Not a valid margin asset.':
            return True
        elif error.error_message == 'The system does not have enough asset now.':
            return True
        elif error.error_message == 'Borrow is banned for this asset.':
            return True
        elif error.error_message == 'Order does not exist.':
            return True
        elif error.error_message == 'Invalid symbol.':
            return True
        elif error.error_message == 'Order would immediately match and take.':
            return True
        elif error.error_message == 'Unknown order sent.':
            return True
        if error.error_message == 'Balance is not enough':
            return True
        elif error.error_message == 'The unpaid debt is too small after this repayment.':
            self.gmailAPIWrapper.send_email('The unpaid debt is too small after this repayment.', '')
            return True
        if error.error_message == 'This isolated margin pair is disabled. Please activate it.':
            return True
        elif error.error_message == 'Balance is not enough':
            return True
        elif error.error_message == 'Not a valid margin asset.':
            return True
        elif error.error_message == 'The system does not have enough asset now.':

            return True
        elif error.error_message == 'Borrow is banned for this asset.':

            self.gmailAPIWrapper.send_email('ban', self.asset)
            return True
        elif error.error_message == 'Asset is not in symbol.':
            return True
        elif error.error_message == 'Repay amount exceeds borrow amount.':
            return True
        elif error.error_message == 'Timestamp for this request is outside of the recvWindow.':
            time.sleep(3)
            return False
        else:
            self.gmailAPIWrapper.send_email('new error', error.error_message)
            return True

    def retry_on_exceptions(retries=5, delays=1, exception_handlers=None):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                for i in range(retries):
                    try:
                        return func(self, *args, **kwargs)
                    except Exception as e:
                        exception_type = type(e)
                        if exception_handlers and exception_type in exception_handlers:
                            should_break = exception_handlers[exception_type](self, e)
                            if should_break:
                                break
                    time.sleep(delays)
                self.gmailAPIWrapper.send_email('my_isolated_margin_account', 'error')
                return None

            return wrapper

        return decorator

    @retry_on_exceptions(5, 1)
    def my_exchange_info(self):
        write_log('Calling my_exchange_info API')
        response = self.client.exchange_info()
        self.rate_limits = response['rateLimits']
        return response

    @retry_on_exceptions(retries=5, delays=1, exception_handlers={
    })
    def my_margin_all_pairs(self):
        write_log('Calling my_margin_all_pairs API')
        response = self.client.margin_all_pairs()
        return response

    @retry_on_exceptions(retries=5, delays=1, exception_handlers={
    })
    def my_isolated_margin_all_pairs(self):
        write_log('Calling my_isolated_margin_all_pairs API')
        response = self.client.isolated_margin_all_pairs()
        return response

    @retry_on_exceptions(retries=5, delays=1, exception_handlers={
    })
    def my_time(self):
        write_log('Calling my_time API')
        response = self.client.time()
        return response

    @retry_on_exceptions(5, 1, exception_handlers={
    })
    def my_account(self):
        write_log('calling my_account api')
        response = self.client.account()
        return response

    @retry_on_exceptions(5, 1, exception_handlers={
    })
    def my_margin_account(self):
        write_log('calling my_margin_account api')
        response = self.client.margin_account()
        return response

    @retry_on_exceptions(10, 1, exception_handlers={ClientError: handle_client_error})
    def my_isolated_margin_account(self):
        """
                response = {'assets': [{'baseAsset': {'asset': ''}}, {'quoteAsset': {'asset': ''}}]}

        :return:
        """
        write_log('api my_isolated_margin_account')

        response = self.client.isolated_margin_account()

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_enable_isolated_margin_account(self, symbol: str):
        """

         response success return is {'success': True, 'symbol': 'KP3RUSDT'}
         it order_type(response)==JSON:
            response['success']

        :param symbol:
        :return:
        """
        write_log('api my_enable_isolated_margin_account', symbol)
        response = self.client.enable_isolated_margin_account(symbol)

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_isolated_margin_transfer(self, asset, symbol, trans_from, trans_to, amount, lot_size):
        """
            Transfer assets between isolated margin and spot accounts.
            Returns:
                dict: A response object with a 'tran_id' key representing the transaction ID, if successful.
                # {'tran_id': 109129467257, 'clientTag': ''}
            Raises:
            Examples
                #>>> response = my_isolated_margin_transfer(self.quote_asset, 'BTCUSDT', 'SPOT', 'ISOLATED_MARGIN', 0.01,  )
               # >>> print(response['tran_id'])
            Notes:
                - Certain errors, such as balance limitations, stop the retry loop immediately.
                response = {'tran_id': ''}
            """
        if trans_from not in ["SPOT", "ISOLATED_MARGIN"]:
            raise ValueError(f"Invalid trans_from value: {trans_from}")

        if trans_to not in ["SPOT", "ISOLATED_MARGIN"]:
            raise ValueError(f"Invalid trans_from value: {trans_from}")

        if asset == self.quote_asset:
            amount = self.asset_amount_filter(asset, amount)

        trans_type = ''
        if trans_from == "SPOT" and trans_to == "ISOLATED_MARGIN":
            trans_type = 'MAIN_ISOLATED_MARGIN'
            kwargs = {'toSymbol': symbol}
        if trans_from == "ISOLATED_MARGIN" and trans_to == "SPOT":
            trans_type = 'ISOLATED_MARGIN_MAIN'
            kwargs = {'fromSymbol': symbol}

        write_log(
            f"calling my_isolated_margin_transfer- {' '.join([trans_type, asset, str(amount)])}   {' '.join([f'{k}={v}' for k, v in kwargs.items()])}")
        response = self.client.user_universal_transfer(trans_type, asset, amount, **kwargs)

        return response

    # todo move this insdie myaccount
    @retry_on_exceptions(10, 1, exception_handlers={ClientError: handle_client_error})
    def my_isolated_margin_account_balance(self, symbol):
        """
        response = 0
        :param symbol:
        :return: usdt balance
        """
        write_log('api my_isolated_margin_account_balance')

        quote_asset = self.quote_asset
        base_asset = symbol[0:-len(quote_asset)]

        response = self.client.isolated_margin_account()

        for i in (self.my_isolated_margin_account()['assets']):
            if i['base_asset']['asset'] == base_asset and i['quote_asset']['asset'] == quote_asset:
                response = float(i['quote_asset']['free'])

        return response

    @retry_on_exceptions(10, 1, exception_handlers={ClientError: handle_client_error})
    def my_cancel_isolated_margin_account(self, symbol):
        """
        response = {'success': False}

                   {'success': True, 'symbol': 'DIAUSDT'}
        :param symbol:
        :return:
        """
        write_log('my_cancel_isolated_margin_account', symbol)

        response = self.client.cancel_isolated_margin_account(symbol)

        return response

    def my_margin_transfer(self, asset, amount, p3):
        """
        response = {'tran_id': ''}
        # {'tran_id': 109130142969, 'clientTag': ''}

        :return:
        """
        write_log('my_margin_transfer', [asset, amount, p3])
        try:
            amount = self.asset_amount_filter(asset, amount)
        except Exception as e:
            print('181', e)

        trans_type = ''
        if str(p3) == '1':
            trans_type = 'MAIN_MARGIN'
        if str(p3) == '2':
            trans_type = 'MARGIN_MAIN'

        response = self.client.user_universal_transfer(trans_type, asset, amount)

        write_log('my_margin_transfer', str(response))

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_klines(self, symbol, interval, **kwargs):
        """
        response = ''
         # [[1654560000000, '2.76400000', '2.79000000', '2.49600000', '2.71400000', '561857.40000000', 1654646399999, '1453695.74610000', 5087, '243207.00000000', '624843.92430000', '0'], [1654646400000, '2.71400000', '2.78500000', '2.56200000', '2.63800000', '281143.90000000', 1654732799999, '749801.57750000', 3469, '177739.30000000', '474380.06740000', '0'], [1654732800000, '2.63200000', '2.79000000', '2.59500000', '2.69700000', '111806.20000000', 1654819199999, '301480.50700000', 1930, '66119.70000000', '178603.06120000', '0'], [1654819200000, '2.70000000', '2.73800000', '2.44300000', '2.48100000', '110035.40000000', 1654905599999, '284596.04530000', 2194, '48573.70000000', '126287.63340000', '0']]

        :param p1:
        :param p2:
        :param p3:
        :return:
        """
        write_log('  api my_klines')
        response = self.client.klines(symbol, interval, **kwargs)

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_depth(self, asset, **params):
        write_log('  api my_depth')

        response = self.client.depth(asset, **params)

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_new_order(self, symbol, side, order_type, **params):
        """
        response = {'orderId': ''}

        """
        write_log('  api my_new_order', str(params))

        response = self.client.new_order(symbol, side, order_type, **params)

        write_log('my_new_order', str(response))

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_margin_order(self, symbol, **params):
        """
         Args:
            symbol (str)
         Keyword Args:
            orderId (str, optional)
            origClientOrderId (str, optional)
            isIsolated (str, optional): for isolated margin or not,"TRUE", "FALSE"，default "FALSE".
            recvWindow (int, optional): The value cannot be greater than 60000
        response = ''
          # {'symbol': 'KP3RUSDT', 'orderId': 205929084, 'clientOrderId': '9jdVYwuLwePIvVVFYovNbd', 'price': '124.63', 'origQty': '8.46', 'executedQty': '8.46', 'cummulativeQuoteQty': '1054.3698', 'status': 'FILLED', 'timeInForce': 'GTC', 'order_type': 'LIMIT_MAKER', 'side': 'SELL', 'stopPrice': '0', 'icebergQty': '0', 'time': 1654887690673, 'updateTime': 1654887690680, 'isWorking': True, 'accountId': 194178931, 'is_isolated': True}

        """
        write_log('  api my_margin_order', [symbol, str(params)])

        response = self.client.margin_order(symbol, **params)

        write_log('my_margin_order', str(response))

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_new_margin_order(self, symbol, side, order_type, **params):
        """
        response = {'orderId': ''}
        error.error_message == 'Order would immediately match and take.':

        ('response ', response['orderId'])
        """
        write_log('  api my_new_margin_order', [symbol, side, order_type, str(params)])

        response = self.client.new_margin_order(symbol, side, order_type, **params)

        write_log('my_new_margin_order', str(response))

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_cancel_margin_order(self, symbol, **params):
        """
        response = {'status': ''}  # 'status': 'CANCELED'
        error.error_message == 'Unknown order sent.':
        # 'Unknown order sent.'  'Isolated margin account does not exist.' 'Invalid symbol.'

                # {'orderId': '205934603', 'symbol': 'KP3RUSDT', 'origClientOrderId': 'sPXOqqEryI4nNoRXmvAOMo', 'clientOrderId': 'Pkb9pNIqHnkscHQaU8xlqH', 'price': '123.98', 'origQty': '8.46', 'executedQty': '0.79', 'cummulativeQuoteQty': '97.9442', 'status': 'CANCELED', 'timeInForce': 'GTC', 'order_type': 'LIMIT_MAKER', 'side': 'BUY', 'is_isolated': True}
                # message='cancel response'+ response+'-----'+response['status']+'-----'+str(order_type(response))

        """

        write_log('my_cancel_margin_order', [symbol, str(params)])

        response = self.client.cancel_margin_order(symbol, **params)
        write_log('my_cancel_margin_order', str(response))

        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_ticker_price(self, symbol):
        write_log('  api my_ticker_price')
        response = self.client.ticker_price(symbol)
        write_log(str(response))
        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_query_repay_record(self, asset, tran_id):
        """
        # {'total': 0, 'rows': []}
           # CONFIRMED'   index error "status": "CONFIRMED",   //one of PENDING (pending execution), CONFIRMED (successfully execution), FAILED (execution failed, nothing happened to your account)
        """
        write_log('  api my_Query_Repay_Record', [asset, tran_id])
        if self.margin_symbol_list[asset] == 'C':
            params = {'asset': asset, 'txId': tran_id}
        else:
            params = {'asset': asset, 'isolatedSymbol': asset + self.quote_asset, 'txId': tran_id}

        response = self.client.borrow_repay_record('REPAY', **params)
        write_log('my_Query_Repay_Record', str(response))
        try:
            result = response['rows'][0]['status']
            return result
        except:
            return None

    def my_margin_repay_until_confirm_sucess(self, asset, amount):
        write_log('  api my_margin_repay_until_confirm_sucess', [asset, amount])
        for i in range(5):
            tran_id = self.my_margin_repay(asset, amount)
            if tran_id is None:
                self.gmailAPIWrapper.send_email('my_margin_repay error', '')
                continue
            response = self.my_query_repay_record(asset, tran_id)
            write_log('my_margin_repay_until_confirm_sucess', str(response))
            if response == 'CONFIRMED':
                return True
            time.sleep(1)
        return None

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_margin_repay(self, asset, amount):
        """
        response {'tran_id': 109133003830, 'clientTag': ''}
        """
        is_isolated = 'FALSE'
        symbol = asset + self.quote_asset
        if self.margin_symbol_list[asset] == 'I':
            is_isolated = 'TRUE'
        current_function_name = inspect.currentframe().f_code.co_name

        write_log(current_function_name, [asset, is_isolated, symbol, amount, 'REPAY'])
        response = self.client.borrow_repay(asset, is_isolated, symbol, amount, 'REPAY')
        write_log(current_function_name, str(response))
        try:
            response = response['tran_id']
            return response
        except:
            return None

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def my_margin_max_transferable(self, asset, **params):
        """
        response = {'amount': 0}
        """
        write_log('  api my_margin_max_transferable', [asset, str(params)])
        # todo can disable a symbol if this usd,so transdfer usd befure disable
        response = self.client.margin_max_transferable(asset, **params)
        write_log('my_margin_max_transferable', str(response))
        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error}
                         )
    def my_margin_max_borrowable(self, asset, **params):
        """
        response = {'amount': 0}
        Args:
            asset (str)
        Keyword Args:
            isolatedSymbol (str, optional): isolated symbol
            recvWindow (int, optional): The value cannot be greater than 60000
        """
        write_log('  api my_margin_max_borrowable  ', asset, str(params))
        response = self.client.margin_max_borrowable(asset, **params)
        return response

    def get_price_deep(self, side, symbol):
        """

        :param side: 'BUY' OR 'SELL'
        :param symbol:
        :return:
        """
        params = {
            'limit': 5
        }
        response = self.my_depth(symbol, **params)

        try:
            bids = response['bids']
            asks = response['asks']
            bid = bids[0][0]
            ask = asks[0][0]
            if side == 'BUY':
                price = bid
            if side == 'SELL':
                price = ask
            return price
        except Exception as e:
            write_log('get_price_deep', e)
            return None

    def get_price_deep_adjust(self, side, symbol):
        params = {
            'limit': 100
        }
        response = self.my_depth(symbol, **params)

        try:
            results_deepth_time = [[datetime.now(), {symbol: response}]]
            df = pd.DataFrame(results_deepth_time)
            df.columns = ['time', 'data']
            csv_filename = './data/q_trade_depth' + str(datetime.now().year) + str(datetime.now().month) + str(
                datetime.now().day) + '.csv'
            df.to_csv(csv_filename, mode='a', header=False, compression='gzip')
        except Exception as e:
            write_log(e)

        try:
            bids = response['bids']
            asks = response['asks']
            bid = bids[0][0]
            s = asks[0][0]
            price_filter = self.price_filter[symbol.replace(self.quote_asset, '')]
            if side == 'BUY':
                if float(s) > float(bid):
                    if math.ceil(bid / price_filter) * price_filter < float(s):
                        price = math.ceil(bid / price_filter) * price_filter
                    else:
                        price = bid
                if s == bid:
                    price = math.ceil(bid / price_filter) * price_filter
                if float(s) < float(bid):
                    price = math.ceil(bid / price_filter) * price_filter
            if side == 'SELL':
                if float(s) > float(bid):
                    math.floor(s / price_filter) * price_filter
                    if math.floor(s / price_filter) * price_filter > float(bid):
                        math.floor(s / price_filter) * price_filter
                    else:
                        price = s
                if s == bid:
                    price = math.floor(s / price_filter) * price_filter
                if float(s) < float(bid):
                    price = math.floor(s / price_filter) * price_filter
            return price
        except Exception as e:
            write_log(e)
            return None

    def get_spot_bnb(self):
        write_log('api my_spot_bnb')
        response = self.client.account()
        for j in response['balances']:
            if j['asset'] == 'BNB':
                response = float(j['free'])
        return response

    @retry_on_exceptions(5, 1, exception_handlers={ClientError: handle_client_error})
    def get_margin_bnb(self):
        write_log('api my_margin_bnb')
        response = self.client.margin_account()
        for j in response['userAssets']:
            if j['asset'] == 'BNB':
                response = float(j['free'])
        return response

    def get_bnb_ready(self):
        bnb_spot = self.my_spot_bnb()
        bnb_margin = self.my_margin_bnb()
        if (bnb_spot + bnb_margin) < 0.05:
            params = {
                'symbol': 'BNBUSDT',
                'side': 'BUY',
                'order_type': 'MARKET',
                'quoteOrderQty': 11
            }
            response = self.my_new_order(**params)
            try:
                order_id = response['orderId']
                print('orderId' + str(order_id))
            except Exception as e:
                print(str(datetime.now()) + 'bnb order not generate sucessful' + e)

        if bnb_spot > bnb_margin:
            if (bnb_spot - bnb_margin) > 0.01:
                self.my_margin_transfer('BNB', (bnb_spot - bnb_margin) / 2, 1)

        if bnb_margin > bnb_spot:
            if (bnb_margin - bnb_spot) > 0.01:
                self.my_margin_transfer('BNB', (bnb_margin - bnb_spot) / 2, 2)

    def get_price_current(self, side, symbol):
        """

        :param side: 'BUY' OR 'SELL'
        :param symbol:
        :return:
        """
        response = self.my_ticker_price(symbol)
        try:
            price_fliter = str(self.price_fliter[symbol.replace(self.quote_asset, '')])
            if side == 'BUY':
                price = math.ceil(float(response['price']) / float(price_fliter)) * float(price_fliter)
            else:
                price = math.floor(float(response['price']) / float(price_fliter)) * float(price_fliter)
            return price
        except Exception as e:
            write_log(e)
            return None

    def borrow(self, symbol, fund_usdt, huilv):
        # fund_usdt, fund can use in cross or isolate
        # symbol BTCUSDT
        print(str(datetime.now()), 'borrow start')
        symbol = symbol.replace("/", "")
        price = huilv
        # todo if max_borrowaswl_in_usdt <100 not borrow

        fund = min(float(self.max_trade_busd_dict[symbol]) * 0.04, fund_usdt * 1.09)
        write_log('min( max_trade_busd_dic',
                  [str(float(self.max_trade_busd_dict[symbol]) * 0.04), str(fund_usdt * 1.09)])
        # if fund < 25:
        # 2023-11.19
        # todo mnium trade fund
        if fund <= 0:
            write_log(str(datetime.now()) + 'not enough fund')

            self.gmailAPIWrapper.send_email('can not borrow 1' + symbol + ' ', '')
            return 0

        return_lot_size = self.lot_size[symbol.replace(self.quote_asset, '')]
        mod_num = int(math.pow(10, return_lot_size))

        if return_lot_size == 0:
            amount_to_trade = int(float(fund) / float(price))
        else:
            amount_to_trade = int(float(fund) / float(price) * mod_num) / mod_num
        print(str(datetime.now()), (symbol.replace(self.quote_asset, ''), amount_to_trade))
        if self.margin_symbol_list[symbol.replace(self.quote_asset, '')] == 'C':
            # todo if not borrow enough in get symbol two, has error here
            borrow_return = self.my_margin_borrow(symbol.replace(self.quote_asset, ''), 'FALSE', symbol,
                                                  amount_to_trade)
        else:
            borrow_return = self.my_margin_borrow(symbol.replace(self.quote_asset, ''), 'TRUE', symbol,
                                                  amount_to_trade)
        print(str(datetime.now()), 'borrow end')
        return borrow_return

    def transfer_all_busd_from_spot_to_margin(self):
        """
        keep my_account update
        :return:
        """
        response = self.my_account()

        balance = response['balances']
        busd = 0
        for i in balance:
            if i['asset'] == self.quote_asset:
                busd = float(i['free']) - 15
        if float(busd) > 0:
            self.my_margin_transfer(self.quote_asset, busd, 1)
        if float(busd) < 0:
            self.my_margin_transfer(self.quote_asset, -busd, 2)

    def transfer_all_asset_from_isolate(self):
        """
        keep my_isolated_margin_account update
        :return:
        """
        response_i = self.my_isolated_margin_account()
        for i in response_i['assets']:
            baseAsset = i['baseAsset']
            quoteAsset = i['quoteAsset']
            if float(quoteAsset['netAsset']) > 0:
                kwargs = {'isolatedSymbol': baseAsset['asset'] + self.quote_asset}
                amount = float(self.my_margin_max_transferable(self.quote_asset, **kwargs)['amount'])
                if float(amount) > 0:
                    if str(self.my_isolated_margin_transfer(self.quote_asset,
                                                            quoteAsset['asset'] + self.quote_asset,
                                                            "ISOLATED_MARGIN",
                                                            "SPOT",
                                                            amount, self.lot_size)['tran_id']) != 0:
                        self.my_margin_transfer(self.quote_asset, amount, 1)
                # if not succeed, try again
                # kwargs = {'isolatedSymbol': baseAsset['asset'] + self.quote_asset}
                # amount = int(float(self.my_margin_max_transferable(self.quote_asset, **kwargs)['amount']) * 0.98)
                # if float(amount) > 0:
                #     if str(self.my_isolated_margin_transfer(self.quote_asset, baseAsset['asset'] + self.quote_asset, "ISOLATED_MARGIN",
                #                                                    "SPOT",
                #                                                    amount, self.lot_size)['tran_id']) != 0:
                #         self.my_margin_transfer(self.quote_asset, amount, 1)

            if float(baseAsset['netAsset']) > 0:
                self.my_isolated_margin_transfer(quoteAsset['asset'], baseAsset['asset'] + self.quote_asset,
                                                 "ISOLATED_MARGIN", "SPOT",
                                                 float(baseAsset['netAsset']), self.lot_size)

    def get_time_difference(self):
        t0 = datetime.now()
        time_server = self.my_time()['serverTime']

        t1 = datetime.now()
        time_delay = (t1 - t0).total_seconds()

        t2 = datetime.now()
        time_server = pd.to_datetime(time_server, unit='ms')

        time_diff = time_server - (t2 - timedelta(seconds=time_delay / 2))

        return time_diff

    def asset_amount_filter(self, asset, amount):
        amount_to_trade = None
        try:
            amount = float(amount)
            lot_size = self.lot_size[asset]
            amount_to_trade = math.floor(amount / lot_size) * lot_size
            return amount_to_trade
        except Exception as e:
            write_log('asset_amount_filter', str(amount), str(amount_to_trade), e)
            return None

    def get_enable_maring_pair(self):
        """need set my_isolated_margin_account to get newsst account info"""
        assets = self.isolated_margin_account['assets']
        tradeble_maring_pair = []
        for asset in assets:
            for attr in asset:
                if attr == 'enabled' and asset['enabled']:
                    tradeble_maring_pair.append(asset['symbol'].replace(self.quote_asset, ''))
        return tradeble_maring_pair

    def get_tradable_marging_pair(self):
        """need set my_isolated_margin_account to get newsst account info"""
        assets = self.isolated_margin_account['assets']
        tradable_marging_pair = []
        for asset in assets:
            for attr in asset:
                if attr == 'symbol':
                    tradable_marging_pair.append(asset['symbol'].replace(self.quote_asset, ''))
        return tradable_marging_pair

    def prepare_borrow_issolate(self):
        margin_iso_pairs = self.get_enable_maring_pair()
        for i in margin_iso_pairs:
            try:
                self.my_isolated_margin_transfer(self.quote_asset, i + self.quote_asset, "SPOT", "ISOLATED_MARGIN",
                                                 0.1,
                                                 self.lot_size)
            except Exception as e:
                print('269', e)

    def finish_borrow_issolate(self):
        margin_iso_pairs = self.get_enable_maring_pair()
        for i in margin_iso_pairs:
            try:
                self.my_isolated_margin_transfer(self.quote_asset, i + self.quote_asset, "ISOLATED_MARGIN", "SPOT",
                                                 0.1,
                                                 self.lot_size)
            except Exception as e:
                print('298', e)

    def get_can_not_trade(self, symbol_isolate):
        symbols_can_not_trade = []
        for symbol in symbol_isolate:
            re = self.my_client_isolated_margin_transfer(self.quote_asset, symbol, "SPOT", "ISOLATED_MARGIN", 0.01,
                                                         self.lot_size)
            if re['tran_id'] == '':
                symbols_can_not_trade.append(symbol)
            return symbols_can_not_trade