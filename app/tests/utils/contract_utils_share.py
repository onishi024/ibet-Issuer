# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app.contracts import Contract
from app.models import ApplyFor
from config import Config

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# 株式トークンの売出
def create_order(issuer, counterpart, share_exchange, token_address, amount, price, agent):
    web3.eth.defaultAccount = issuer['account_address']
    web3.personal.unlockAccount(issuer['account_address'], issuer['password'])

    ShareContract = Contract.get_contract('IbetShare', token_address)
    tx_hash = ShareContract.functions.transfer(share_exchange['address'], amount) \
        .transact({'from': issuer['account_address']})
    web3.eth.waitForTransactionReceipt(tx_hash)

    ExchangeContract = Contract.get_contract('IbetOTCExchange', share_exchange['address'])
    tx_hash = ExchangeContract.functions.createOrder(
        counterpart['account_address'],
        token_address,
        amount,
        price,
        agent['account_address']
    ). \
        transact({'from': issuer['account_address'], 'gas': 4000000})


# 直近注文IDを取得
def get_latest_orderid(share_exchange):
    ExchangeContract = Contract.get_contract('IbetOTCExchange', share_exchange['address'])
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid


# 直近約定IDを取得
def get_latest_agreementid(share_exchange, order_id):
    ExchangeContract = Contract.get_contract(
        'IbetOTCExchange', share_exchange['address'])
    latest_agreementid = ExchangeContract.functions.latestAgreementId(order_id).call()
    return latest_agreementid


# 株式トークンの買いTake注文
def take_buy(invoker, share_exchange, order_id):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])

    ExchangeContract = Contract.get_contract('IbetOTCExchange', share_exchange['address'])
    tx_hash = ExchangeContract.functions.executeOrder(order_id). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 株式約定の資金決済
def confirm_agreement(invoker, share_exchange, order_id, agreement_id):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])

    ExchangeContract = Contract.get_contract(
        'IbetOTCExchange', share_exchange['address'])

    tx_hash = ExchangeContract.functions. \
        confirmAgreement(order_id, agreement_id). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 会員権：募集申込
def apply_for_offering(db, invoker, token_address):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'], invoker['password'])
    TokenContract = Contract.get_contract('IbetShare', token_address)
    tx_hash = TokenContract.functions.applyForOffering(1, 'abcdefgh'). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)

    # 募集申込イベント登録
    apply_for = ApplyFor()
    apply_for.transaction_hash = tx_hash
    apply_for.token_address = token_address
    apply_for.account_address = invoker['account_address']
    apply_for.amount = 1
    db.session.add(apply_for)
