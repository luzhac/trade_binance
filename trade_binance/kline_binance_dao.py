import asyncio
import inspect
import json
from datetime import datetime

import aiohttp

from trade_binance.utils import GmailAPIWrapper , write_log,

class KlineBinanceDAO:
    def __init__(self):
        self.kline_results_symbols = []
        self.kline_results = []

        self.kline_results_symbols_2 = []
        self.kline_results_2 = []

        self.gmailAPIWrapper=GmailAPIWrapper()

    async def gather_with_concurrency(self, n, urls, conn, symbol_base, maxtime_in_data):

        try:
            semaphore = asyncio.Semaphore(n)
            session = aiohttp.ClientSession(connector=conn)

            async def get(i, retries=5, backoff_factor=1):
                for attempt in range(retries):
                    async with semaphore:
                        try:
                            async with session.get(urls[i][0], ssl=False, ) as response:
                                status_code = response.status
                                if status_code == 200:
                                    if maxtime_in_data is None:
                                        self.kline_results_symbols.append(urls[i][2])
                                    else:
                                        self.kline_results_symbols_2.append(urls[i][2])
                                    obj = json.loads(await response.read())
                                    for j in obj:
                                        if maxtime_in_data is None:
                                            modified_j = [j[0], j[1], j[4], j[5]]
                                            modified_j.append(i + symbol_base)
                                            self.kline_results.append(modified_j)
                                        else:
                                            if j[0] == maxtime_in_data:
                                                modified_j = [j[0], j[1], j[4], j[5]]
                                                modified_j.append(i + symbol_base)
                                                self.kline_results_2.append(modified_j)
                                    return
                                elif response.status == 429:
                                    self.gmailAPIWrapper.send_email('429', 'gather_with_concurrency')
                                    return
                                elif status_code == 503:
                                    pass
                                else:

                                    print(f"Attempt {attempt + 1} failed with status code {status_code}")
                        except asyncio.TimeoutError:

                            print(f"Attempt {attempt + 1} failed with error: TimeoutError")

                        except aiohttp.ClientError as e:

                            print(f"Attempt {attempt + 1} failed with error: {e}")

                    sleep_time = backoff_factor * (2 ** attempt)
                    print(f"Retrying in {sleep_time} seconds...")
                    await asyncio.sleep(sleep_time)

                self.gmailAPIWrapper.send_email('exception get symbols', '')
                print('All retry attempts failed.')

            await asyncio.gather(*(get(i) for i in urls))
            await session.close()

        except Exception as e:
            self.gmailAPIWrapper.send_email('exception get symbols', '')

            write_log('1584', e)
        finally:
            await session.close()

    def get_binance_margin_klines_data(self, interval, limit, maxtime_in_data,quote_asset,margin_asset_list):
        """
        # https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=300
        """
        if maxtime_in_data is None:
            self.kline_results = []
            self.kline_results_symbols = []
        else:
            self.kline_results_2 = []
            self.kline_results_symbols_2 = []
        start_time = datetime.now()
        print(datetime.now(), 'get symbol start <-----')
        urls = {}
        quote_asset = quote_asset
        for index, (key, value) in enumerate(margin_asset_list.items()):
            urls[key] = [
                'https://api.binance.com/api/v3/klines?symbol=' + key + quote_asset + '&interval=' + interval + '&limit=' + str(
                    limit), index, key]

        conn = aiohttp.TCPConnector(limit_per_host=400, limit=400, ttl_dns_cache=400)
        PARALLEL_REQUESTS = 400
        asyncio.run(
            self.gather_with_concurrency(PARALLEL_REQUESTS, urls, conn, quote_asset, maxtime_in_data))
        conn.close()
        end_time = datetime.now()
        print(end_time, 'get symbol end <-----')
        print('time used', str((end_time - start_time).total_seconds()))

        if maxtime_in_data is None:
            print(
                f"Total {len(urls)} completed {len(self.kline_results_symbols)} requests with {len(self.kline_results)} results")
        else:
            print(
                f"Total {len(urls)} completed {len(self.kline_results_symbols_2)} requests with {len(self.kline_results_2)} results")

        if len(urls) != len(self.kline_results_symbols):
            self.gmailAPIWrapper.send_email('Total not equal completed', '')
            return None
        if (end_time - start_time).total_seconds() > 9:
            print('over 9 seconds')
            self.gmailAPIWrapper.send_email('over 9 seconds klines', str((datetime.now() - start_time).total_seconds()))
            return self.kline_results
        else:
            return self.kline_results