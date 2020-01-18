# -*- coding: utf-8 -*-
import json
import base64

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

from config import Config
from app.contracts import Contract
from .account_config import eth_account

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# 名簿用個人情報登録
# NOTE: issuer address に対する情報の公開を行う
def register_personal_info(invoker, personal_info, encrypted_info):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personal_info['address'])

    issuer = eth_account['issuer']
    tx_hash = PersonalInfoContract.functions.register(issuer['account_address'], encrypted_info). \
        transact({'from': invoker['account_address'], 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)

# personalInfoの暗号済情報を復号化して返す
def get_personal_encrypted_info(personal_info, account_address, token_owner):
    # personalinfo取得
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personal_info['address'])
    encrypted_info = PersonalInfoContract.functions.personal_info(
        to_checksum_address(account_address),
        to_checksum_address(token_owner)
    ).call()[2]
    # 復号化
    key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
    cipher = PKCS1_OAEP.new(key)
    ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
    message = cipher.decrypt(ciphertext)
    return json.loads(message)