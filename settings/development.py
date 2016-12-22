import os

DEBUG = True
SECRET_KEY = "A not very secret value only for mock-up purposes of course"

# API
OPENID_PROVIDER = "https://auth-sandbox.ebury.io"
API_ENDPOINT = "https://sandbox.ebury.io"
API_KEY = os.getenv('API_KEY')

# OpenID Provider
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
STATE = os.getenv('STATE')

# Xero credentials
XERO_CONSUMER_KEY = os.getenv('XERO_CONSUMER_KEY')
XERO_SIGNING_KEY = open(os.getenv('XERO_SIGNING_KEY'), 'rt').read()
