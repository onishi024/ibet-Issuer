# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware
from config import Config
from app.contracts import Contract
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# クーポン：募集申込
def apply_for_offering(invoker, token_address):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])
    TokenContract = Contract.get_contract('IbetCoupon', token_address)
    gas = TokenContract.estimateGas().applyForOffering('abcdefgh')
    tx_hash = TokenContract.functions.applyForOffering('abcdefgh'). \
        transact({'from': invoker['account_address'], 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)
