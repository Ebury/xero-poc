from base64 import b64encode
from urllib.parse import urlencode
from urllib3 import PoolManager, disable_warnings
from json import loads, dumps
from base64 import b64decode

from simple_settings import settings

from datetime import datetime, timedelta

from xero.constants import XERO_BASE_URL, XERO_API_URL

import logging
import requests

disable_warnings()
logger = logging.getLogger(__name__)


class APIConnection(PoolManager):
    """ Simple connection pool for calling the API
    """
    def __init__(self, app):
        """When this initialises grab a session token"""
        super(APIConnection, self).__init__()
        self.host = settings.API_ENDPOINT
        self.headers = {'x-api-key': settings.API_KEY}
        self.tokens = {}

    def __call__(self, method, uri, user_id, body=None, headers={}):
        try:
            token = self.tokens[user_id.id]

            headers.update(self.headers)
            headers['X-Contact-ID'] = user_id.id
            headers['Authorization'] = 'Bearer {}'.format(token['access_token'])
            logger.debug("Sending headers: %s" % headers)
            logger.debug("Data: {}".format(body))
            response = self.urlopen(method,
                                    '{}{}client_id={}'.format(self.host, uri, token['jwt_payload']['clients'][0]),
                                    body=body,
                                    headers=headers)
            logger.debug("Response data: {}".format(response.data))
            return response

        except Exception as e:
            logger.error('Unhandled exception calling API', exc_info=True)
            raise Exception('API Connection Error', 'API call failed')

    def future_date(self):
        now = datetime.now()

        return (now + timedelta(days=3)).strftime("%Y-%m-%d") \
            if (now + timedelta(days=1)).weekday() in [5, 6] \
            else (now + timedelta(days=1)).strftime("%Y-%m-%d")

    def cache_token(self, contact_id, token):
        self.tokens[contact_id] = token

    def get_quote(self, user_id, sell_currency, buy_currency, amount):
        return self('POST',
                    '/quotes?quote_type=quote&',
                    user_id,
                    body=dumps({
                        'amount': float(amount),
                        'buy_currency': buy_currency,
                        'operation': 'buy',
                        'sell_currency': sell_currency,
                        'trade_type': 'spot',
                        'value_date': self.future_date()
                    }))

    def book_trade(self, user_id, quote_id):
        return self('POST',
                    '/trades?quote_id={}&'.format(quote_id),
                    user_id,
                    body=dumps({
                        'trade_type': 'spot',
                        'rate_direction': 'direct',
                        'reason': 'Accounts payable'
                    }))

    def get_beneficiary(self, user_id, beneficiary_id):
        return self('GET',
                    '/beneficiaries/{}?'.format(beneficiary_id),
                    user_id)

    def create_beneficiary(self, user_id, beneficiary):
        """ OF COURSE THIS SHOULD BE METADATA DRIVEN!!!
        :param user_id:
        :param beneficiary:
        :return:
        """
        return self('POST',
                    '/beneficiaries?',
                    user_id,
                    body=dumps({
                        'name': beneficiary['name'],
                        'email_notification':  beneficiary['email_notification'],
                        'address_line_1':  beneficiary['address_line_1'],
                        'post_code':  beneficiary['post_code'],
                        'country_code':  beneficiary['country_code'],
                        'bank_country_code': beneficiary['bank_country_code'],
                        'bank_currency_code': beneficiary['bank_currency_code'],
                        'bank_name': beneficiary['account_name'],
                        'account_number': beneficiary['account_number'],
                        'iban': beneficiary['iban'],
                        'swift_code': beneficiary['swift_code']
                    }))

    def create_payment(self, user_id, trade_id, beneficiary_id, account_id, amount, xero_contact_id):
        payment_date = self.future_date()
        response = self('POST',
                    '/payments?',
                    user_id,
                    body=dumps({
                        'trade_id': trade_id,
                        'payments': [{
                            'beneficiary_id': beneficiary_id,
                            'account_id': account_id,
                            'amount': float(amount),
                            'email_beneficiary': True,
                            'payment_date': payment_date,
                            'reference': xero_contact_id
                        }]
                    }))
        response.payment_date = payment_date
        return response


class TokenConnection(PoolManager):
    """ Simple connection pool for calling the Token endpoint
    """
    def __init__(self, app):
        super().__init__()
        self.token_endpoint = '{}/token'.format(settings.OPENID_PROVIDER)
        self.redirect_uri = settings.REDIRECT_URI
        self.headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic %s' % b64encode(bytes('%s:%s' % (settings.CLIENT_ID, settings.CLIENT_SECRET), 'utf-8')).decode('utf-8')
        }
        self.tokens = {}

    def __call__(self, code):
        body = urlencode({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'state': settings.STATE
        })

        return self.urlopen('POST', self.token_endpoint, headers=self.headers, body=body)

    def get_token(self, code):
        response = self(code)

        if response.status == 200:
            logger.debug(response)
            response_data = loads(response.data.decode('utf-8'))

            # Decode JWT and get clients
            jwt_payload = loads(b64decode(bytes(response_data['id_token'].split('.')[1], 'utf-8')).decode('utf-8'))
            cached_token = {
                'access_token': response_data['access_token'],
                'refresh_token': response_data['refresh_token'],
                'jwt_payload': jwt_payload
            }

            self.tokens[jwt_payload['sub']] = cached_token
            logger.debug(self.tokens)
            return jwt_payload['sub'], cached_token, response

        logger.error("Status: {}, data: {}".format(response.status, response.data))
        return


class XeroConnection:
    def __init__(self, oauth):
        self.payments_url = '{}{}/Payments'.format(XERO_BASE_URL, XERO_API_URL)
        self.oauth = oauth

    def create_payment(self, xero, invoice_id, payment_date, rate, amount, trade_id):
        # Make an assumption from demo account
        xero_account = xero.accounts.filter(Name='Business Bank Account').pop()

        # Just lazy...
        xero_payment = '<Payments>' \
                       '<Payment>' \
                       '<Invoice>' \
                       '<InvoiceID>{}</InvoiceID>' \
                       ' </Invoice>' \
                       '<Account>' \
                       '<AccountID>{}</AccountID>' \
                       '</Account>' \
                       '<Date>{}</Date>' \
                       '<CurrencyRate>{}</CurrencyRate>' \
                       '<Amount>{}</Amount>' \
                       '<Reference>{}</Reference>' \
                       '</Payment>' \
                       '</Payments>'.format(invoice_id, xero_account['AccountID'], payment_date, rate, amount, trade_id)

        response = requests.put(self.payments_url, data=xero_payment, auth=self.oauth)
        return response
