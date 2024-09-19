import asyncio
import hashlib
import hmac
import inspect
import json
import os
import pickle
import time
from datetime import datetime, timedelta



from trade_binance.binance_api_wrapper import BinanceAPIWrapper
from trade_binance.utils import write_log,  \
    get_config


class StrategyAPI(BinanceAPIWrapper):
    def __init__(self):
        # Inherit the initialization from the base class
        super().__init__()

        self.results_borrow = []
        self.symbols_can_not_trade = []
        self.update()

    def update(self):
        super().update()
        #self.set_can_not_trade(self.margin_isolate_asset_list)

    def set_can_not_trade(self,symbol_isolate):
        symbols_can_not_trade = []
        for symbol in symbol_isolate:
            response = self.my_isolated_margin_transfer(self.quote_asset, symbol+self.quote_asset, "SPOT", "ISOLATED_MARGIN", 0.01)
            if response is None:
                symbols_can_not_trade.append(symbol)
        self.symbols_can_not_trade=symbols_can_not_trade


    def get_spot_bnb(self):
        write_log('api my_spot_bnb')
        response = self.my_account()
        for j in response['balances']:
            if j['asset'] == 'BNB':
                response = float(j['free'])
        return response

    def get_margin_bnb(self):
        write_log('api my_margin_bnb')
        response = self.my_margin_account()
        for j in response['userAssets']:
            if j['asset'] == 'BNB':
                response = float(j['free'])
        return response
    def get_bnb_ready(self):
        bnb_spot = self.get_spot_bnb()
        bnb_margin = self.get_margin_bnb()
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
                print(str(datetime.now()) + 'bnb order not generate sucessful' + str(e))

        if bnb_spot > bnb_margin:
            if (bnb_spot - bnb_margin) > 0.01:
                self.my_margin_transfer('BNB', (bnb_spot - bnb_margin) / 2, 1)

        if bnb_margin > bnb_spot:
            if (bnb_margin - bnb_spot) > 0.01:
                self.my_margin_transfer('BNB', (bnb_margin - bnb_spot) / 2, 2)






