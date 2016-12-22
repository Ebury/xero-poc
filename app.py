#!/usr/bin/env python

# TODO: Webargs on each of the views to validate API calls and map to backend calls due to my shoddy workmanship
# TODO: Obviously needs some serious cleaning up of the incomplete workflow i.e. traded but didn't pay, for example
# TODO: Cut this script down, it's very looooooonggggg...

from flask import Flask, request, make_response, render_template, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_login import login_required, LoginManager, UserMixin, login_user, logout_user, current_user

from client import TokenConnection, APIConnection, XeroConnection
from simple_settings import settings

from json import loads, dumps

from xero import Xero
from xero.auth import PrivateCredentials

import logging

logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] [%(name)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.update(settings.as_dict())
login_manager = LoginManager(app)
xero_credentials = PrivateCredentials(settings.XERO_CONSUMER_KEY, settings.XERO_SIGNING_KEY)
xero = Xero(xero_credentials)

Bootstrap(app)

# Connection pools for hitting the token endpoint API
TOKEN_CONNECTION = TokenConnection(app)
API_CONNECTION = APIConnection(app)
XERO_CONNECTION = XeroConnection(xero_credentials.oauth)


class EburyUser(UserMixin):
    pass


def get_xero_contact(xero_contact_id):
    return xero.contacts.get(xero_contact_id).pop()


@login_manager.user_loader
def user_loader(contact_id):
    if contact_id not in TOKEN_CONNECTION.tokens:
        return

    user = EburyUser()
    user.id = contact_id
    return user


@app.errorhandler(Exception)
def unhandled_error(exception):
    """ Generic exception handler
    :return:
    """
    logger.error("Unhandled exception", exc_info=True)

    response = make_response('Unhandled exception on server', 500)
    response.headers['Content-Type'] = 'text/plain'
    return response


@app.errorhandler(401)
def login_prompt(exception):
    return redirect('/')


@app.route('/')
def index():
    """ Serve up the authentication page
    :return:
    """

    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    return render_template("index.html",
                           timing=2,
                           openid_provider=settings.OPENID_PROVIDER,
                           client_id=settings.CLIENT_ID,
                           state=settings.STATE,
                           redirect_uri=settings.REDIRECT_URI)


@app.route("/callback")
def callback():
    """
    Redirect following successful authentication and token creation. Of course, this would normally be served on the
    client. The client would then do something really clever, etc....
    """
    # TODO: Defensive coding
    # TODO: Added JWT verifier
    authorization_code = request.args.get('code')

    if authorization_code:
        try:
            contact_id, token, response = TOKEN_CONNECTION.get_token(authorization_code)
            API_CONNECTION.cache_token(contact_id, token)

            if contact_id:
                user = EburyUser()
                user.id = contact_id
                login_user(user)
                return redirect("/dashboard")

            logger.error("Error response: %s" % response.data)
            return make_response('Unexpected response from token endpoint, see server logs: {}'.format(response.status),
                                 500)

        except:
            logger.error('Unknown error processing callback', exc_info=True)
            return make_response('Unknown error processing callback', 500)

    return make_response('', 400)


@app.route('/dashboard')
@login_required
def dashboard():
    # logger.debug(xero.invoices.all())

    return render_template('dashboard.html', invoices=[invoice for invoice in xero.invoices.filter(
        Status='AUTHORISED', Type='ACCPAY') if invoice['CurrencyCode'] != 'GBP'])


@app.route('/quote', methods=['POST'])
@login_required
def quote():
    currency_pair = request.get_json()

    if currency_pair is None:
        return make_response(dumps({'error': 'No currencies found in payload'}), 400)

    quote = API_CONNECTION.get_quote(current_user,
                                     currency_pair['sell'],
                                     currency_pair['buy'],
                                     currency_pair['amount'])

    response = make_response(quote.data, quote.status)
    response.headers['Content-Type'] = 'application/json'
    return response


@app.route('/trade', methods=['POST'])
@login_required
def trade():
    request_payload = request.get_json()
    booked_trade = API_CONNECTION.book_trade(current_user, request_payload['quote_id'])
    xero_contacts = []

    if booked_trade.status == 201:
        trade_data = loads(booked_trade.data.decode('utf-8'))
        logger.debug(trade_data)

        for contact in request_payload['contacts']:
            xero_details = get_xero_contact(contact['contact_id'])
            logger.debug(xero_details)

            beneficiary = {
                    'xero_contact_id': contact['contact_id'],
                    'ebury_beneficiary_id': xero_details.get('ContactNumber', ''),
                    'invoice_id': contact['invoice_id'],
                    'name': xero_details['Name'],
                    'country_code': '',
                    'bank_country_code': '',
                    'bank_currency_code': '',
                    'account_name': xero_details.get('BatchPayments', {}).get('BankAccountName', ''),
                    'account_number': xero_details.get('BatchPayments', {}).get('BankAccountNumber', ''),
                    'iban': '',
                    'swift_code': '',
                    'trade_id': trade_data['trade_id'],
                    'currency': request_payload['currency'],
                    'amount': contact['amount'],
                    'rate': request_payload['rate']
                }

            if 'ContactNumber' in xero_details.keys():
                # When a beneficiary is provisioned we'll link it to the Xero account
                # Make a call to get existing beneficiary details
                # Overwrite the details from Xero
                existing_details = API_CONNECTION.get_beneficiary(current_user, xero_details['ContactNumber'])

                if existing_details.status != 200:
                    return make_response(existing_details.data, existing_details.status)

                existing_beneficiary = loads(existing_details.data.decode('utf-8'))
                accounts = existing_beneficiary.get('bank_accounts', [])

                if len(accounts) > 0:
                    beneficiary.update(
                        {
                            'account_id': accounts[0].get('account_id', ''),
                            'country_code': existing_beneficiary.get('country_code', ''),
                            'bank_country_code': accounts[0].get('bank_country_code', ''),
                            'bank_currency_code': accounts[0].get('bank_currency_code', ''),
                            'account_name': accounts[0].get('bank_name', ''),
                            'account_number': accounts[0].get('account_number', ''),
                            'iban': accounts[0].get('iban', ''),
                            'swift_code': accounts[0].get('swift_code', '')
                        }
                    )

            xero_contacts.append(beneficiary)

        trade_data['contacts'] = xero_contacts
        response = make_response(dumps(trade_data))
        response.headers['Content-Type'] = 'application/json'
        return response

    response = make_response(booked_trade.data, booked_trade.status)
    response.headers['Content-Type'] = 'application/json'
    return response


@app.route('/pay', methods=['POST'])
@login_required
def pay():
    request_payload = request.get_json()

    for payment in request_payload:
        if payment['ebury_beneficiary_id'] == '':
            xero_details = get_xero_contact(payment['xero_contact_id'])

            # Fairly aggressive, needs a better approach
            address = [address for address in xero_details.get('Addresses', [])
                       if address['AddressType'] == 'STREET'].pop()

            payment.update({
                'email_notification': True,
                'address_line_1': 'Default',
                'post_code': address['PostalCode'],
            })
            beneficiary_response = API_CONNECTION.create_beneficiary(current_user, payment)

            if beneficiary_response.status != 201:
                return make_response(beneficiary_response.data, beneficiary_response.status)

            # Add new beneficiary details to payment
            new_beneficiary = loads(beneficiary_response.data.decode('utf-8'))
            payment.update({
                'ebury_beneficiary_id': new_beneficiary['beneficiary_id'],
                'account_id': str(new_beneficiary['account_id'])
            })

            xero_details['ContactNumber'] = loads(beneficiary_response.data.decode('utf-8'))['beneficiary_id']
            xero.contacts.save(xero_details)

        # Now add payment to trade and payment to Xero
        payment_response = API_CONNECTION.create_payment(current_user,
                                                         payment['trade_id'],
                                                         payment['ebury_beneficiary_id'],
                                                         payment['account_id'],
                                                         payment['amount'],
                                                         payment['xero_contact_id'])

        if payment_response.status != 201:
            return make_response(payment_response.data, payment_response.status)

        # Need an account to assign the payment to in Xero
        xero_response = XERO_CONNECTION.create_payment(xero, payment['invoice_id'], payment_response.payment_date,
                                                       payment['rate'], payment['amount'], payment['trade_id'])

        if xero_response.raw.status != 200:
            for each in xero_response.__dict__.items():
                logger.debug(each)
            return make_response(xero_response.raw.data, xero_response.raw.status)

    return make_response('', 204)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect('/')

if __name__ == "__main__":
    app.run(port=5001, debug=settings.DEBUG)
