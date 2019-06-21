# -*- coding: utf-8 -*-
import os
import json
import base64
import argparse
import time
import sys

path = os.path.join(os.path.dirname(__file__), "../")
sys.path.append(path)

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address
from app.contracts import Contract

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from app.models import Token
from config import Config


WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

ETH_ACCOUNT = os.environ.get('ETH_ACCOUNT') or web3.eth.accounts[0]
ETH_ACCOUNT = to_checksum_address(ETH_ACCOUNT)
ETH_ACCOUNT_PASSWORD = os.environ.get('ETH_ACCOUNT_PASSWORD')
TOKEN_LIST_CONTRACT_ADDRESS = to_checksum_address(os.environ.get('TOKEN_LIST_CONTRACT_ADDRESS'))
IBET_SB_EXCHANGE_CONTRACT_ADDRESS = \
    to_checksum_address(os.environ.get('IBET_SB_EXCHANGE_CONTRACT_ADDRESS'))
IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = \
    to_checksum_address(os.environ.get('IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS'))
IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = \
    to_checksum_address(os.environ.get('IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS'))

# DB
URI = os.environ.get("DATABASE_URL")
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

# トークン発行
def issue_token(exchange_address, data_count, token_type):
    attribute = {}
    attribute['name'] = 'SEINO_TEST_TOKEN'
    attribute['symbol'] = 'SEINO'
    attribute['totalSupply'] = data_count
    attribute['tradableExchange'] = exchange_address
    attribute['memo'] = 'memo'
    attribute['details'] = 'details'
    attribute['expirationDate'] = '20181010'
    attribute['transferable'] = True
    attribute['status'] = True
    attribute['contactInformation'] = '08012345678'
    attribute['privacyPolicy'] = 'プライバシーポリシーの内容'

    if token_type == 'IbetStraightBond':
        attribute['faceValue'] = 100
        attribute['interestRate'] = 1
        attribute['interestPaymentDate1'] = '20181010'
        attribute['redemptionDate'] = '20181010'
        attribute['redemptionAmount'] = 100
        attribute['returnDate'] = '20181010'
        attribute['returnAmount'] = 'returnAmount'
        attribute['purpose'] = 'purpose'
        interestPaymentDate = json.dumps({
            'interestPaymentDate1':attribute['interestPaymentDate1']
        })
        arguments = [
            attribute['name'], attribute['symbol'], attribute['totalSupply'],
            attribute['tradableExchange'],
            attribute['faceValue'], attribute['interestRate'], interestPaymentDate,
            attribute['redemptionDate'], attribute['redemptionAmount'],
            attribute['returnDate'], attribute['returnAmount'],
            attribute['purpose'], attribute['memo'],
            attribute['status'], attribute['contactInformation'], attribute['privacyPolicy']
        ]
        template_id = Config.TEMPLATE_ID_SB
    elif token_type == 'IbetMembership':
        attribute['returnDetails'] = 'returnDetails'
        arguments = [
            attribute['name'], attribute['symbol'], attribute['totalSupply'],
            attribute['tradableExchange'],
            attribute['details'], attribute['returnDetails'],
            attribute['expirationDate'], attribute['memo'],
            attribute['transferable'],
            attribute['status'], attribute['contactInformation'], attribute['privacyPolicy']
        ]
        template_id = Config.TEMPLATE_ID_MEMBERSHIP
    elif token_type == 'IbetCoupon':
        arguments = [
            attribute['name'], attribute['symbol'], attribute['totalSupply'],
            attribute['tradableExchange'],
            attribute['details'],  attribute['memo'], attribute['expirationDate'],
            attribute['transferable'],
            attribute['status'], attribute['contactInformation'], attribute['privacyPolicy']
        ]
        template_id = Config.TEMPLATE_ID_COUPON

    web3.eth.defaultAccount = ETH_ACCOUNT
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD)
    _, bytecode, bytecode_runtime = Contract.get_contract_info(token_type)
    contract_address, abi, tx_hash = Contract.deploy_contract(token_type, arguments, ETH_ACCOUNT)

    # db_session
    token = Token()
    token.template_id = template_id
    token.tx_hash = tx_hash
    token.admin_address = None
    token.token_address = None
    token.abi = str(abi)
    token.bytecode = bytecode
    token.bytecode_runtime = bytecode_runtime
    db_session.merge(token)
    db_session.commit()
    return {'address': contract_address, 'abi': abi}

# トークンリスト登録
def register_token_list(token_dict, token_type):
    TokenListContract = Contract.get_contract('TokenList', TOKEN_LIST_CONTRACT_ADDRESS)
    web3.eth.defaultAccount = ETH_ACCOUNT
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD)
    tx_hash = TokenListContract.functions.register(token_dict['address'], token_type).\
        transact({'from':ETH_ACCOUNT, 'gas':4000000})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)
    print("TokenListContract Length:" + str(TokenListContract.functions.getListLength().call()))


def main(data_count, token_type):
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 10000)
    if token_type == 'IbetStraightBond':
        exchange_address = IBET_SB_EXCHANGE_CONTRACT_ADDRESS
    elif token_type == 'IbetMembership':
        exchange_address = IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
    elif token_type == 'IbetCoupon':
        exchange_address = IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    print("exchange_address: " + exchange_address)
    # token登録
    for count in range(0, data_count):
        # トークン発行
        token_dict = issue_token(exchange_address, data_count, token_type)
        # トークンリストに登録
        register_token_list(token_dict, token_type)
        print("count: " + str(count))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="トークンの登録")
    parser.add_argument("data_count", type=int, help="登録件数")
    parser.add_argument("token_type", type=str, help="IbetStraightBond, IbetMembership, IbetCoupon")
    args = parser.parse_args()

    if not args.data_count:
        raise Exception("登録件数が必要")

    if not args.token_type:
        raise Exception("IbetStraightBond, IbetMembership, IbetCoupon")

    main(args.data_count, args.token_type)