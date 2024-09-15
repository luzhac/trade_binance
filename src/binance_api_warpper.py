
import time
from binance.error import ClientError
from binance.spot import Spot
from src.utils import get_env_variable, GmailSender, write_log,get_config


class BinanceAPIWrapper:

    def __init__(self):
        if get_config('environment')=='development':
            self.client = Spot('',
                               '')
        else:
            self.client = Spot(api_key=get_env_variable('api_key'),
                           api_secret=get_env_variable('api_secret'))

        self.list4 = {}

        self.huilv_zero = {}
        self.after_zero = {}
        self.huilv = {}

        self.asset = ''
        self.symbol = ''
        self.is_isolated=''
        self.amount=''
        self.tran_id=''

        self.gmailSender = GmailSender()



    def handle_connection_error(self, e):
        write_log(f"ConnectionError: {e}")
        time.sleep(1)  # Wait longer before retrying
        return False

    def handle_index_error(self, e):
        write_log(f"handle_index_error: {e}")
        self.gmailSender.send_email('index error.', '413')
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
        elif error.error_message == 'Timestamp for this request is outside of the recvWindow.':
            time.sleep(3)
            return False
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
            self.gmailSender.send_email('The unpaid debt is too small after this repayment.', '')
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
            self.gmailSender.send_message('ban', self.asset)
            return True
        elif error.error_message == 'Asset is not in symbol.':
            return True
        elif error.error_message == 'Repay amount exceeds borrow amount.':
            return True
        else:
            self.gmailSender.send_message('new error', error.error_message)
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

                    time.sleep(delays)
                self.gmailAPIWrapper.send_email('my_isolated_margin_account', 'error')
                return None

            return wrapper

        return decorator

    @retry_on_exceptions(5, 1)
    def my_exchange_info(self):
        write_log('Calling my_exchange_info API')
        response = self.client.exchange_info()
        return response


