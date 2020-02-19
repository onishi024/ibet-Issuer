# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware
from config import Config
from app.contracts import Contract

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# 直近注文IDを取得
def get_latest_orderid(membership_exchange):
    ExchangeContract = Contract.get_contract('IbetMembershipExchange', membership_exchange['address'])
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid


# 直近約定IDを取得
def get_latest_agreementid(membership_exchange, order_id):
    ExchangeContract = Contract.get_contract(
        'IbetMembershipExchange', membership_exchange['address'])
    latest_agreementid = ExchangeContract.functions.latestAgreementId(order_id).call()
    return latest_agreementid


# 会員権トークンの買いTake注文
def take_buy(invoker, membership_exchange, order_id, amount):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])

    ExchangeContract = Contract.get_contract('IbetMembershipExchange', membership_exchange['address'])
    tx_hash = ExchangeContract.functions.executeOrder(order_id, amount, True). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 会員権約定の資金決済
def confirm_agreement(invoker, membership_exchange, order_id, agreement_id):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    ExchangeContract = Contract.get_contract(
        'IbetMembershipExchange', membership_exchange['address'])

    tx_hash = ExchangeContract.functions. \
        confirmAgreement(order_id, agreement_id). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 会員権：募集申込
def apply_for_offering(invoker, token_address):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])
    TokenContract = Contract.get_contract('IbetMembership', token_address)
    tx_hash = TokenContract.functions.applyForOffering('abcdefgh'). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)
