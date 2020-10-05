# -*- coding: utf-8 -*-

from web3 import Web3
from web3.middleware import geth_poa_middleware

from app.utils import ContractUtils
from config import Config
from .account_config import eth_account

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# 決済用銀行口座情報登録
def register_only_payment_account(invoker, payment_gateway, encrypted_info):
    PaymentGatewayContract = ContractUtils.get_contract(
        'PaymentGateway', payment_gateway['address'])

    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    agent = eth_account['agent']
    tx_hash = PaymentGatewayContract.functions.register(agent['account_address'], encrypted_info). \
        transact({'from': invoker['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)

# 決済口座の認可
def approve_payment_account(invoker, payment_gateway):
    PaymentGatewayContract = ContractUtils.get_contract(
        'PaymentGateway', payment_gateway['address'])
    agent = eth_account['agent']

    # 2) 認可 from Agent
    web3.eth.defaultAccount = agent['account_address']
    web3.personal.unlockAccount(agent['account_address'], agent['password'])

    tx_hash = PaymentGatewayContract.functions.approve(invoker['account_address']). \
        transact({'from': agent['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 決済用銀行口座情報登録（認可まで）
def register_payment_account(invoker, payment_gateway, encrypted_info):
    PaymentGatewayContract = ContractUtils.get_contract(
        'PaymentGateway', payment_gateway['address'])

    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    agent = eth_account['agent']
    tx_hash = PaymentGatewayContract.functions.register(agent['account_address'], encrypted_info). \
        transact({'from': invoker['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)

    # 2) 認可 from Agent
    web3.eth.defaultAccount = agent['account_address']
    web3.personal.unlockAccount(agent['account_address'], agent['password'])

    tx_hash = PaymentGatewayContract.functions.approve(invoker['account_address']). \
        transact({'from': agent['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)
