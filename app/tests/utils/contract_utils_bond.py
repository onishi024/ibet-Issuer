# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware
from config import Config
from app.contracts import Contract
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# 直近注文IDを取得
def get_latest_orderid(bond_exchange):
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', bond_exchange['address'])
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid

# 直近約定IDを取得
def get_latest_agreementid(bond_exchange, order_id):
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', bond_exchange['address'])
    latest_agreementid = ExchangeContract.functions.latestAgreementId(order_id).call()
    return latest_agreementid

# 募集申込
def bond_apply_for_offering(invoker, token_address):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])
    TokenContract = Contract.get_contract('IbetStraightBond', token_address)
    tx_hash = TokenContract.functions.applyForOffering(1,'abcdefgh'). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)
