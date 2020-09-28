# -*- coding: utf-8 -*-

from web3 import Web3
from web3.middleware import geth_poa_middleware

from config import Config
from app.utils import ContractUtils
from .account_config import eth_account

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# 名簿用個人情報登録
# NOTE: issuer address に対する情報の公開を行う
def register_personal_info(invoker, personal_info, encrypted_info):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    PersonalInfoContract = ContractUtils.get_contract(
        'PersonalInfo', personal_info['address'])

    issuer = eth_account['issuer']
    tx_hash = PersonalInfoContract.functions.register(issuer['account_address'], encrypted_info). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)
