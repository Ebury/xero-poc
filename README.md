Getting Started
---------------

To use the Xero & Ebury POC for the first time:
```
virtualenv -p [/path/to/python3.4] [/path/to/venv]
source [/path/to/venv]/bin/activate
cd xero-poc
pip install -r requirements.txt

export API_KEY = _<YOUR_API_KEY>_
export CLIENT_ID = _<YOUR_CLIENT_ID>_
export CLIENT_SECRET = _<YOUR_CLIENT_SECRET >_
export REDIRECT_URI = _<YOUR_REDIRECT_URI>_
export STATE = _<YOUR_STATE>_
export XERO_CONSUMER_KEY = _<YOUR_XERO_CONSUMER_KEY>_
export XERO_SIGNING_KEY = <YOUR_XERO_SIGNING_KEY>

export SIMPLE_SETTINGS=settings.development

./app.py
```