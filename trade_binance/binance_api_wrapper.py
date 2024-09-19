
import inspect
import math
import time

import pandas as pd

from datetime import datetime, timedelta

from binance.error import ClientError
from binance.spot import Spot

from trade_binance.utils import write_log, get_env_variable, \
    GmailAPIWrapper, get_config

class BinanceAPIWrapper:
    def __init__(self):

        api_key = get_env_variable('api_key')
        api_secret = get_env_variable('api_secret')
        if not api_key or not api_secret:
            raise EnvironmentError("Config variable 'api_key' or 'api_secret' is missing")

        environment = get_config('environment')
        if environment == 'development':
            self.client = Spot(api_key=api_key, api_secret=api_secret)
        else:
            self.client = Spot(api_key=api_key, api_secret=api_secret)  # Use real credentials in production

        self.quote_asset = get_config('quote_asset')
        if not self.quote_asset:
            raise EnvironmentError("Config variable 'quote_asset' is missing")

        self.asset=None
        self.symbol=None

        self.rate_limits = None

        self.margin_asset_list = {}

        self.margin_isolate_asset_list = []

        self.spot_symbol_list = {}
        
        self.price_filter = {}
        self.lot_size = {}

        self.exchange_rate = {}

        self.max_trade_busd_dict={}

        self.isolated_margin_account=None

        self.gmailAPIWrapper = GmailAPIWrapper()

        self.update()

    def update(self):
        self.set_filter()

        self.update_exchange_rate()

    def update_exchange_rate(self):
        exchange_rate_df = pd.read_csv('../data/q_last_exchange_rate.csv',index_col=0,skiprows=1)

        exchange_rate_df.columns = ['close']
        for index, row in exchange_rate_df.iterrows():
            self.exchange_rate[index.replace(self.quote_asset, '')] = float(row['close'])
        self.exchange_rate[self.quote_asset] = 1





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
            row_base_asset = row['baseAsset']
            row_quote_asset = row['quoteAsset']
            filter_out = False
            if not  row_quote_asset:
                write_log(f"set filter Missing quote asset for symbol: {row}")
                continue
            if row_quote_asset != self.quote_asset:
                continue
            if get_config('assets1'):
                if row_base_asset in [base_asset  for base_asset in
                                          get_config('assets1')]:
                    filter_out = True
            if not filter_out:
                if row_quote_asset == self.quote_asset and row['status'] == 'TRADING':
                    quote_precision=row['quotePrecision']
                    if not self.price_filter.get(row_quote_asset):
                        self.price_filter[row_quote_asset]= round(0.1**int(quote_precision), quote_precision)
                    if not self.lot_size.get(row_quote_asset):
                        self.lot_size[row_quote_asset]= round(0.1**int(quote_precision), quote_precision)
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

    def get_time_difference(self):
        t0 = datetime.now()
        time_server = self.my_time()['serverTime']

        t1 = datetime.now()
        time_delay = (t1 - t0).total_seconds()

        t2 = datetime.now()
        time_server = pd.to_datetime(time_server, unit='ms')

        time_diff = time_server - (t2 - timedelta(seconds=time_delay / 2))

        return time_diff

    def asset_lot_size_filter(self, asset, amount):
        amount_to_trade = None
        try:
            amount = float(amount)
            lot_size = self.lot_size[asset]
            amount_to_trade=math.floor(amount/lot_size)*lot_size
            return amount_to_trade
        except Exception as e:
            write_log('asset_lot_size_filter', str(amount), str(amount_to_trade), e)
            return None

    def asset_price_filter(self, asset, amount):
        amount_to_trade = None
        try:
            amount = float(amount)
            lot_size = self.price_filter[asset]
            amount_to_trade=math.floor(amount/lot_size)*lot_size
            return amount_to_trade
        except Exception as e:
            write_log('asset_price_filter', str(amount), str(amount_to_trade), e)
            return None

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

    def retry_on_exceptions(retries = 5, delays=1, exception_handlers=None):
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
                        write_log(f"Retrying {func.__name__} after exception: {e}")
                    time.sleep(delays)
                self.gmailAPIWrapper.send_email('my_isolated_margin_account', 'error')
                return None
            return wrapper

        return decorator

    @retry_on_exceptions(5, 1)
    def my_exchange_info(self):
        write_log('Calling my_exchange_info API')
        response = self.client.exchange_info()
        self.rate_limits=response['rateLimits']
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
    def my_funding_wallet(self):
        write_log('calling my_account api')
        response = self.client.funding_wallet()
        return response

    @retry_on_exceptions(5, 1, exception_handlers={
    })
    def my_margin_account(self):
        write_log('calling my_margin_account api')
        response = self.client.margin_account()
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
            amount = self.asset_lot_size_filter(asset, amount)
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
    def my_ticker_price(self, symbol):
        write_log('  api my_ticker_price')
        response = self.client.ticker_price(symbol)
        write_log(str(response))
        return response











    def get_price_deep_adjust(self, side, symbol):
        params = {
            'limit': 100
        }
        response = self.my_depth(symbol, **params)

        try:
            results_depth_time = [[datetime.now(), {symbol: response}]]
            df = pd.DataFrame(results_depth_time)
            df.columns = ['time', 'data']
            csv_filename = '../data/q_trade_depth' + str(datetime.now().year) + str(datetime.now().month) + str(
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
            price = None
            if side == 'BUY':
                if float(s) > float(bid):
                    if  math.ceil(bid/price_filter)*price_filter < float(s):
                        price = math.ceil(bid/price_filter)*price_filter
                    else:
                        price = bid
                if s == bid:
                    price =  math.ceil(bid/price_filter)*price_filter
                if float(s) < float(bid):
                    price =  math.ceil(bid/price_filter)*price_filter
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
        
    def get_price_current(self, side, symbol):
        """
        :param side: 'BUY' OR 'SELL'
        :param symbol:
        :return:
        """
        response = self.my_ticker_price(symbol)
        try:
            price_filter = str(self.price_filter[symbol.replace(self.quote_asset, '')])
            price=None
            if side == 'BUY':
                price = math.ceil(float(response['price']) / float(price_filter)) * float(price_filter)
            if side == 'SELL':
                price = math.floor(float(response['price']) / float(price_filter)) * float(price_filter)
            return price
        except Exception as e:
            write_log(e)
            return None

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
            bid= bids[0][0]
            ask = asks[0][0]
            price=None
            if side == 'BUY':
                price = bid
            if side == 'SELL':
                price = ask
            return price
        except Exception as e:
            write_log('get_price_deep',e)
            return None












