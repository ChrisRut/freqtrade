import json
import logging
import requests
import numpy as np

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class CryptoML(object):

    def __init__(self, whitelist, api_key, api_version="v1"):
        self.logger = logging.getLogger(__name__)
        self.logger.level = logging.INFO  # DEBUG is VERY verbose, comment out this line if you need to debug
        self.logger.debug("loading CryptoML()...")
        self.name = 'cryptoml'
        if api_version == "v1":
            self.url = "https://cryptoml.azure-api.net/prediction/threshold/"
            self.payload = '{}'
        else:
            self.url = "https://cryptoml.azure-api.net/v2/prediction/threshold/"
            self.payload = None
        self.headers = {
            'content-type': "application/json",
            'ocp-apim-subscription-key': api_key,
        }

        self.whitelist = whitelist
        self.predictions = 0
        self.buy_signal_buffer = {}
        self.reset_buffer()

    def reset_buffer(self):
        self.logger.debug("reset_buffer()")
        self.buy_signal_buffer = {}
        for market in self.whitelist:
            self.buy_signal_buffer[market] = {
                'buy_count': 0,
                'predicted_returns': [],
                'running_return': 0
            }

    def get_cryptoml_predictions(self, threshold=0.025):
        self.logger.debug(f"get_cryptoml_predictions(threshold={threshold})")
        args = {
            'method': 'POST',
            'url': self.url + str(threshold),
            'headers': self.headers
        }
        if self.payload:
            args['data'] = self.payload
        self.logger.debug(f"calling {self.url}{threshold} with headers ({self.headers}) and payload ({self.payload})")
        r = requests.request(**args)

        if r.status_code != 200:
            self.logger.error(f"non-200 response code while calling {self.url}{threshold}\nargs: {args}\ncode: {r.status_code}\nresponse: {r.text}")
            return {}
        self.logger.debug(f"get_cryptoml_predictions, return: {r.text}")
        return r.json()

    def update_buy_buffer(self, threshold=0.025):
        self.logger.debug(f"update_buy_buffer(threshold={threshold})")
        resp = self.get_cryptoml_predictions(threshold)
        self.predictions = len(resp.keys())
        self.logger.debug(f"looping over {len(self.buy_signal_buffer)} markets: {self.buy_signal_buffer.keys()}")
        for market in self.buy_signal_buffer:
            coin = market[4:]
            if coin in resp:
                if resp[coin]:
                    self.buy_signal_buffer[market]['buy_count'] += 1
                    self.buy_signal_buffer[market]['predicted_returns'].append(resp[coin][0]['score'])
                    self.buy_signal_buffer[market]['running_return'] = np.asarray(
                        self.buy_signal_buffer[market]['predicted_returns']
                    ).mean()
                else:
                    self.buy_signal_buffer[market]['buy_count'] = 0
                    self.buy_signal_buffer[market]['predicted_returns'] = []
                    self.buy_signal_buffer[market]['running_return'] = 0

    def get_buy_signal(self, threshold=0.025, repeats=3):
        self.logger.debug(f"get_buy_signal(threshold={threshold}, repeats={repeats})")

        # optionally update buy buffer
        self.update_buy_buffer(threshold)
        zero_buy_count = [k for k, v in self.buy_signal_buffer.items() if v['buy_count'] == 0]
        self.logger.debug(f"zero_buy_count: {zero_buy_count}")
        non_zero_buy_count = [{k: v} for k, v in self.buy_signal_buffer.items() if v['buy_count'] > 0]
        self.logger.debug(f"non_zero_buy_count: {non_zero_buy_count}")

        # Provide summary
        self.logger.info(f"CryptoML made {self.predictions} predictions, from that we found {len(non_zero_buy_count)} coins that we should potentially buy: {json.dumps(non_zero_buy_count, indent=2)}")

        return non_zero_buy_count
