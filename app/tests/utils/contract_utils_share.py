# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app.utils import ContractUtils
from app.models import ApplyFor
from config import Config

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


# SHAREトークンの売出
def create_order(issuer, counterpart, share_exchange, token_address, amount, price, agent):
    web3.eth.defaultAccount = issuer['account_address']
    ShareContract = ContractUtils.get_contract('IbetShare', token_address)
    tx_hash = ShareContract.functions.transfer(share_exchange['address'], amount) \
        .transact({'from': issuer['account_address']})
    web3.eth.waitForTransactionReceipt(tx_hash)

    ExchangeContract = ContractUtils.get_contract('IbetOTCExchange', share_exchange['address'])
    ExchangeContract.functions.createOrder(
        counterpart['account_address'],
        token_address,
        amount,
        price,
        agent['account_address']
    ).transact({'from': issuer['account_address'], 'gas': Config.TX_GAS_LIMIT})


# 直近注文IDを取得
def get_latest_orderid(share_exchange):
    ExchangeContract = ContractUtils.get_contract('IbetOTCExchange', share_exchange['address'])
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid


# 直近約定IDを取得
def get_latest_agreementid(share_exchange, order_id):
    ExchangeContract = ContractUtils.get_contract(
        'IbetOTCExchange', share_exchange['address'])
    latest_agreementid = ExchangeContract.functions.latestAgreementId(order_id).call()
    return latest_agreementid


# SHAREトークンの買いTake注文
def take_buy(invoker, share_exchange, order_id):
    web3.eth.defaultAccount = invoker['account_address']
    ExchangeContract = ContractUtils.get_contract('IbetOTCExchange', share_exchange['address'])
    tx_hash = ExchangeContract.functions.executeOrder(order_id). \
        transact({'from': invoker['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 約定の資金決済
def confirm_agreement(invoker, share_exchange, order_id, agreement_id):
    web3.eth.defaultAccount = invoker['account_address']
    ExchangeContract = ContractUtils.get_contract(
        'IbetOTCExchange', share_exchange['address'])

    tx_hash = ExchangeContract.functions. \
        confirmAgreement(order_id, agreement_id). \
        transact({'from': invoker['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 募集申込
def apply_for_offering(db, invoker, token_address):
    web3.eth.defaultAccount = invoker['account_address']
    TokenContract = ContractUtils.get_contract('IbetShare', token_address)
    tx_hash = TokenContract.functions.applyForOffering(1, 'abcdefgh'). \
        transact({'from': invoker['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)

    # 募集申込イベント登録
    apply_for = ApplyFor()
    apply_for.transaction_hash = tx_hash
    apply_for.token_address = token_address
    apply_for.account_address = invoker['account_address']
    apply_for.amount = 1
    db.session.add(apply_for)
