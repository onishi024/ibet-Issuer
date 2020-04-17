# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware

from config import Config
from app.contracts import Contract

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# アドレス認可済み確認
def is_address_authorized(token, target_token):
    ShareTokenContract = Contract.get_contract('IbetShare', token.token_address)
    is_authorized = ShareTokenContract.functions.authorizedAddress(target_token).call()
    return is_authorized
