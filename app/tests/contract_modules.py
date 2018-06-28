# -*- coding: utf-8 -*-
import time
import json
import os
import sqlalchemy as sa
import base64
from base64 import b64encode

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

from config import Config
from .account_config import eth_account
from .contract_config import IbetStraightBond, PersonalInfo, TokenList
from ..models import Token

from logging import getLogger
logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# 株主名簿用個人情報登録
def register_personalinfo(invoker, personal_info, encrypted_info):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    PersonalInfoContract = web3.eth.contract(
        address=personal_info['address'], abi=personal_info['abi'])

    issuer = eth_account['issuer']
    tx_hash = PersonalInfoContract.functions.register(issuer['account_address'], encrypted_info).\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)


# 決済用銀行口座情報登録
def register_only_whitelist(invoker, white_list, encrypted_info):
    WhiteListContract = web3.eth.contract(
        address=white_list['address'], abi=white_list['abi'])

    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    agent = eth_account['agent']
    tx_hash = WhiteListContract.functions.register(agent['account_address'], encrypted_info).\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

# 決済口座の認可
def approve_whitelist(invoker, white_list):
    WhiteListContract = web3.eth.contract(
        address=white_list['address'], abi=white_list['abi'])
    agent = eth_account['agent']

    # 2) 認可 from Agent
    web3.eth.defaultAccount = agent['account_address']
    web3.personal.unlockAccount(agent['account_address'], agent['password'])

    tx_hash = WhiteListContract.functions.approve(invoker['account_address']).\
        transact({'from':agent['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)



# 決済用銀行口座情報登録（認可まで）
def register_whitelist(invoker, white_list, encrypted_info):
    WhiteListContract = web3.eth.contract(
        address=white_list['address'], abi=white_list['abi'])

    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    agent = eth_account['agent']
    tx_hash = WhiteListContract.functions.register(agent['account_address'], encrypted_info).\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

    # 2) 認可 from Agent
    web3.eth.defaultAccount = agent['account_address']
    web3.personal.unlockAccount(agent['account_address'], agent['password'])

    tx_hash = WhiteListContract.functions.approve(invoker['account_address']).\
        transact({'from':agent['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)


# 債券トークンの発行
def issue_bond_token(invoker, attribute):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    abi = IbetStraightBond['abi']
    bytecode = IbetStraightBond['bytecode']
    bytecode_runtime = IbetStraightBond['bytecode_runtime']

    TokenContract = web3.eth.contract(
        abi=abi,
        bytecode=bytecode,
        bytecode_runtime=bytecode_runtime,
    )

    interestPaymentDate = json.dumps({
        'interestPaymentDate1':attribute['interestPaymentDate1'],
        'interestPaymentDate2':attribute['interestPaymentDate2'],
        'interestPaymentDate3':attribute['interestPaymentDate3'],
        'interestPaymentDate4':attribute['interestPaymentDate4'],
        'interestPaymentDate5':attribute['interestPaymentDate5'],
        'interestPaymentDate6':attribute['interestPaymentDate6'],
        'interestPaymentDate7':attribute['interestPaymentDate7'],
        'interestPaymentDate8':attribute['interestPaymentDate8'],
        'interestPaymentDate9':attribute['interestPaymentDate9'],
        'interestPaymentDate10':attribute['interestPaymentDate10'],
        'interestPaymentDate11':attribute['interestPaymentDate11'],
        'interestPaymentDate12':attribute['interestPaymentDate12']
    })

    arguments = [
        attribute['name'], attribute['symbol'], attribute['totalSupply'],
        attribute['faceValue'], attribute['interestRate'], interestPaymentDate,
        attribute['redemptionDate'], attribute['redemptionAmount'],
        attribute['returnDate'], attribute['returnAmount'],
        attribute['purpose'], attribute['memo']
    ]

    tx_hash = TokenContract.deploy(
        transaction={
            'from': invoker['account_address'],
            'gas': 4000000
        },
        args=arguments).hex()

    tx = wait_transaction_receipt(tx_hash)

    contract_address = ''
    if tx is not None:
        # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
        if 'contractAddress' in tx.keys():
            contract_address = tx['contractAddress']

    return {'address': contract_address, 'abi': IbetStraightBond['abi']}


# 債券トークンのリスト登録
def register_bond_list(invoker, bond_token, token_list):
    TokenListContract = web3.eth.contract(
        address=token_list['address'], abi=token_list['abi'])

    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    tx_hash = TokenListContract.functions.register(bond_token['address'], 'IbetStraightBond').\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

# 債券トークンの募集
def offer_bond_token(invoker, bond_exchange, bond_token, amount, price):
    bond_transfer_to_exchange(invoker, bond_exchange, bond_token, amount)
    make_sell_bond_token(invoker, bond_exchange, bond_token, amount, price)

# 取引コントラクトに債券トークンをチャージ
def bond_transfer_to_exchange(invoker, bond_exchange, bond_token, amount):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    TokenContract = web3.eth.contract(
        address=bond_token['address'], abi=bond_token['abi'])

    tx_hash = TokenContract.functions.transfer(bond_exchange['address'], amount).\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

# 債券トークンの売りMake注文
def make_sell_bond_token(invoker, bond_exchange, bond_token, amount, price):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],invoker['password'])

    ExchangeContract = web3.eth.contract(
        address=bond_exchange['address'], abi=bond_exchange['abi'])

    agent = eth_account['agent']

    gas = ExchangeContract.estimateGas().\
        createOrder(bond_token['address'], amount, price, False, agent['account_address'])
    tx_hash = ExchangeContract.functions.\
        createOrder(bond_token['address'], amount, price, False, agent['account_address']).\
        transact({'from':invoker['account_address'], 'gas':gas})
    tx = wait_transaction_receipt(tx_hash)

# 債券トークンの買いTake注文
def take_buy_bond_token(invoker, bond_exchange, order_id, amount):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    ExchangeContract = web3.eth.contract(
        address=bond_exchange['address'], abi=bond_exchange['abi'])

    tx_hash = ExchangeContract.functions.\
        executeOrder(order_id, amount, True).\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

# 直近注文IDを取得
def get_latest_orderid(bond_exchange):
    ExchangeContract = web3.eth.contract(
        address=bond_exchange['address'], abi=bond_exchange['abi'])
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid

# 直近約定IDを取得
def get_latest_agreementid(bond_exchange, order_id):
    ExchangeContract = web3.eth.contract(
        address=bond_exchange['address'], abi=bond_exchange['abi'])
    latest_agreementid = ExchangeContract.functions.latestAgreementIds(order_id).call()
    return latest_agreementid

# 債券約定の資金決済
def bond_confirm_agreement(invoker, bond_exchange, order_id, agreement_id):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    ExchangeContract = web3.eth.contract(
        address=bond_exchange['address'], abi=bond_exchange['abi'])

    tx_hash = ExchangeContract.functions.\
        confirmAgreement(order_id, agreement_id).\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

# トークン数取得
def get_token_list_length(token_list):
    ListContract = web3.eth.contract(
        address = to_checksum_address(token_list['address']),
        abi = token_list['abi'],
    )
    list_length = ListContract.functions.getListLength().call()
    return list_length

# トークン数取得
def get_token_list(token_list, token_address):
    ListContract = web3.eth.contract(
        address = to_checksum_address(token_list['address']),
        abi = token_list['abi'],
    )
    token = ListContract.functions.getTokenByAddress(token_address).call()
    return token

# 認定実施
def exec_sign(token_address, token_abi, invoker):
    web3.eth.defaultAccount = invoker['account_address']
    web3.personal.unlockAccount(invoker['account_address'],
                                invoker['password'])

    token_abi = json.loads(token_abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address = token_address,
        abi = token_abi
    )
    tx_hash = TokenContract.functions.sign().\
        transact({'from':invoker['account_address'], 'gas':4000000})
    tx = wait_transaction_receipt(tx_hash)

# 認定区分を取得
def get_signature(token_address, token_abi, signer_address):
    token_abi = json.loads(token_abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address = token_address,
        abi = token_abi
    )
    return TokenContract.functions.signatures(signer_address).call()

# personalInfoを復号化して返す
def get_personal_encrypted_info(personal_info, account_address, token_owner):
    # personalinfo取得
    PersonalInfoContract = web3.eth.contract(
        address=personal_info['address'], abi=personal_info['abi'])
    encrypted_info = PersonalInfoContract.functions.personal_info(
                to_checksum_address(account_address), 
                to_checksum_address(token_owner)
        ).call()[2]
    # 復号化
    key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
    cipher = PKCS1_OAEP.new(key)
    ciphertext = base64.decodestring(encrypted_info.encode('utf-8'))
    message = cipher.decrypt(ciphertext)
    return json.loads(message)

# whitelistを復号化して返す
def get_whitelist_encrypted_info(white_list, account_address, agent_address):
    WhiteListContract = web3.eth.contract(
        address=white_list['address'], abi=white_list['abi'])
    payment_account = WhiteListContract.functions.payment_accounts(
            to_checksum_address(account_address),
            to_checksum_address(agent_address)
        ).call()
    logger.info(payment_account)
    # 復号化
    key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
    cipher = PKCS1_OAEP.new(key)
    ciphertext = base64.decodestring(payment_account[2].encode('utf-8'))
    message = cipher.decrypt(ciphertext)
    return json.loads(message)


# トランザクションがブロックに取り込まれるまで待つ
# 10秒以上経過した場合は失敗とみなす（Falseを返す）
def wait_transaction_receipt(tx_hash):
    count = 0
    tx = None

    while True:
        time.sleep(0.1)
        try:
            tx = web3.eth.getTransactionReceipt(tx_hash)
        except:
            continue

        count += 1
        if tx is not None:
            break
        elif count > 120:
            raise Exception

    return tx


# 発行済みトークンのアドレスをDBへ登録
def processorIssueEvent(db):
    # コントラクトアドレスが登録されていないTokenの一覧を抽出
    tokens = Token.query.all()
    for token in tokens:
        if token.token_address is None:
            tx_hash = token.tx_hash
            tx_hash_hex = '0x' + tx_hash[2:]
            try:
                tx_receipt = wait_transaction_receipt(tx_hash_hex)
            except:
                continue
            if tx_receipt is not None :
                # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
                if 'contractAddress' in tx_receipt.keys():
                    admin_address = tx_receipt['from']
                    contract_address = tx_receipt['contractAddress']

                    # 登録済みトークン情報に発行者のアドレスと、トークンアドレスの登録を行う。
                    token.admin_address = admin_address
                    token.token_address = contract_address
                    db.session.add(token)