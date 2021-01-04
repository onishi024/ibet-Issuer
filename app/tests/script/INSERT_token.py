"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

import argparse
import os
import sys

path = os.path.join(os.path.dirname(__file__), "../../..")
sys.path.append(path)

from web3 import Web3
from web3.middleware import geth_poa_middleware
from app.utils import ContractUtils

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from app.models import Token, Issuer
from config import Config


WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# DB
URI = os.environ.get("DATABASE_URL") or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)


# トークン発行
def issue_token(exchange_address, data_count, token_type, issuer):
    attribute = {}
    attribute['name'] = 'SEINO_TEST_TOKEN'
    attribute['symbol'] = 'SEINO'
    attribute['totalSupply'] = data_count
    attribute['tradableExchange'] = exchange_address
    attribute['memo'] = 'memo'
    attribute['details'] = 'details'
    attribute['expirationDate'] = '20181010'
    attribute['transferable'] = True
    attribute['contactInformation'] = '08012345678'
    attribute['privacyPolicy'] = 'プライバシーポリシーの内容'

    if token_type == 'IbetStraightBond':
        attribute['faceValue'] = 100
        attribute['redemptionDate'] = '20181010'
        attribute['redemptionValue'] = 100
        attribute['returnDate'] = '20181010'
        attribute['returnDetails'] = 'returnDetails'
        attribute['purpose'] = 'purpose'

        arguments = [
            attribute['name'], attribute['symbol'], attribute['totalSupply'],
            attribute['faceValue'],
            attribute['redemptionDate'], attribute['redemptionValue'],
            attribute['returnDate'], attribute['returnDetails'],
            attribute['purpose'],
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
            attribute['contactInformation'], attribute['privacyPolicy']
        ]
        template_id = Config.TEMPLATE_ID_MEMBERSHIP
    elif token_type == 'IbetCoupon':
        attribute['returnDetails'] = 'returnDetails'
        arguments = [
            attribute['name'], attribute['symbol'], attribute['totalSupply'],
            attribute['tradableExchange'],
            attribute['details'], attribute['returnDetails'],
            attribute['memo'], attribute['expirationDate'],
            attribute['transferable'],
            attribute['contactInformation'], attribute['privacyPolicy']
        ]
        template_id = Config.TEMPLATE_ID_COUPON
    elif token_type == 'IbetShare':
        attribute['personalInfoAddress'] = '0x0000000000000000000000000000000000000000'
        attribute['issuePrice'] = 100
        attribute['dividends'] = 10
        attribute['dividendRecordDate'] = '20181010'
        attribute['dividendPaymentDate'] = '20181010'
        attribute['cancellationDate'] = '20181010'
        arguments = [
            attribute['name'], attribute['symbol'],
            attribute['tradableExchange'], attribute['personalInfoAddress'],
            attribute['issuePrice'], attribute['totalSupply'],
            attribute['dividends'], attribute['dividendRecordDate'], attribute['dividendPaymentDate'],
            attribute['cancellationDate'],
            attribute['contactInformation'], attribute['privacyPolicy'],
            attribute['memo'],
            attribute['transferable']
        ]
        template_id = Config.TEMPLATE_ID_SHARE

    _, bytecode, bytecode_runtime = ContractUtils.get_contract_info(token_type)
    contract_address, abi, tx_hash = ContractUtils.deploy_contract(
        token_type, arguments, issuer.eth_account, db_session=db_session)

    if token_type == 'IbetStraightBond':
        contract = ContractUtils.get_contract('IbetStraightBond', contract_address)
        tx = contract.functions.setTradableExchange(exchange_address). \
            buildTransaction({'from': issuer.eth_account})
        ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)

    # db_session
    token = Token()
    token.template_id = template_id
    token.tx_hash = tx_hash
    token.admin_address = issuer.eth_account.lower()
    token.token_address = None
    token.abi = str(abi)
    token.bytecode = bytecode
    token.bytecode_runtime = bytecode_runtime
    db_session.merge(token)
    db_session.commit()
    return {'address': contract_address, 'abi': abi}


# トークンリスト登録
def register_token_list(token_dict, token_type, issuer):
    TokenListContract = ContractUtils.get_contract('TokenList', issuer.token_list_contract_address)
    tx = TokenListContract.functions.register(token_dict['address'], token_type).\
        buildTransaction({'from': issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
    ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)
    print("TokenListContract Length:" + str(TokenListContract.functions.getListLength().call()))


def main(data_count, token_type, issuer):
    if token_type == 'IbetStraightBond':
        exchange_address = issuer.ibet_sb_exchange_contract_address
    elif token_type == 'IbetMembership':
        exchange_address = issuer.ibet_membership_exchange_contract_address
    elif token_type == 'IbetCoupon':
        exchange_address = issuer.ibet_coupon_exchange_contract_address
    elif token_type == 'IbetShare':
        exchange_address = issuer.ibet_share_exchange_contract_address
    print("exchange_address: " + exchange_address)
    # token登録
    for count in range(0, data_count):
        # トークン発行
        token_dict = issue_token(exchange_address, data_count, token_type, issuer)
        # トークンリストに登録
        register_token_list(token_dict, token_type, issuer)
        print("count: " + str(count))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="トークンの登録")
    parser.add_argument("data_count", type=int, help="登録件数")
    parser.add_argument("token_type", type=str, help="IbetStraightBond, IbetMembership, IbetCoupon, IbetShare")
    parser.add_argument("--issuer", '-s', type=str, help="発行体アドレス")
    args = parser.parse_args()

    if not args.data_count:
        raise Exception("登録件数が必要")

    if not args.token_type:
        raise Exception("IbetStraightBond, IbetMembership, IbetCoupon, IbetShare")

    issuer_address = args.issuer if args.issuer is not None else web3.eth.accounts[0]
    issuer_model = db_session.query(Issuer).filter(Issuer.eth_account == issuer_address).first()
    if issuer_model is None:
        raise Exception("発行体が未登録です")
    print(f'発行体アドレス: {issuer_model.eth_account}')

    main(args.data_count, args.token_type, issuer_model)
