"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

import os
import argparse
import sys
from cryptography.fernet import Fernet

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

URI = os.environ.get("DATABASE_URL") or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

fernet = Fernet(os.environ['SECURE_PARAMETER_ENCRYPTION_KEY'].encode())

issuer_encrypted_info = ''
trader_encrypted_info = ''


# トークン発行
def issue_token(exchange_address, data_count, token_type, issuer):
    attribute = {
        'name': 'SEINO_TEST_COUPON_CONSUME_' + str(data_count),
        'symbol': 'SEINO',
        'totalSupply': data_count,
        'tradableExchange': exchange_address,
        'memo': 'memo',
        'details': 'details',
        'returnDetails': 'returnDetails',
        'expirationDate': '20181010',
        'transferable': True,
        'status': True,
        'contactInformation': '08012345678',
        'privacyPolicy': 'プライバシーポリシーの内容'
    }

    arguments = [
        attribute['name'], attribute['symbol'], attribute['totalSupply'],
        attribute['tradableExchange'],
        attribute['details'], attribute['returnDetails'],
        attribute['memo'], attribute['expirationDate'],
        attribute['transferable'],
        attribute['contactInformation'], attribute['privacyPolicy']
    ]
    template_id = Config.TEMPLATE_ID_COUPON

    _, bytecode, bytecode_runtime = ContractUtils.get_contract_info(token_type)
    contract_address, abi, tx_hash = ContractUtils.deploy_contract(token_type, arguments, issuer.eth_account,
                                                                   db_session=db_session)

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
    tx = TokenListContract.functions.register(token_dict['address'], token_type). \
        buildTransaction({'from': issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
    ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)
    print("TokenListContract Length:" + str(TokenListContract.functions.getListLength().call()))


# トークン売出(売り)
def offer_token(agent_address, exchange_address, token_dict, amount, token_type, ExchangeContract, issuer):
    transfer_to_exchange(exchange_address, token_dict, amount, token_type, issuer)
    make_sell_token(agent_address, token_dict, amount, ExchangeContract, issuer)


# 取引コントラクトにトークンをチャージ
def transfer_to_exchange(exchange_address, token_dict, amount, token_type, issuer):
    TokenContract = ContractUtils.get_contract(token_type, token_dict['address'])
    tx = TokenContract.functions.transfer(exchange_address, amount). \
        buildTransaction({'from': issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
    ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)
    print("transfer_to_exchange:balanceOf exchange_address:" + str(TokenContract.functions.balanceOf(exchange_address).call()))


# トークンの売りMake注文
def make_sell_token(agent_address, token_dict, amount, ExchangeContract, issuer):
    tx = ExchangeContract.functions. \
        createOrder(token_dict['address'], amount, 100, False, agent_address). \
        buildTransaction({'from': issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
    ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)


# 直近注文IDを取得
def get_latest_orderid(ExchangeContract):
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid


# 直近約定IDを取得
def get_latest_agreement_id(ExchangeContract, order_id):
    latest_agreement_id = ExchangeContract.functions.latestAgreementId(order_id).call()
    return latest_agreement_id


# トークンの買いTake注文
def buy_coupon_token(trader_address, ExchangeContract, order_id, amount):
    web3.eth.defaultAccount = trader_address
    web3.personal.unlockAccount(trader_address, 'password')
    tx_hash = ExchangeContract.functions. \
        executeOrder(order_id, amount, True). \
        transact({'from': trader_address, 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 株主名簿用個人情報登録
def register_personalinfo(invoker_address, encrypted_info, issuer):
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, 'password')
    PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', issuer.personal_info_contract_address)

    tx_hash = PersonalInfoContract.functions.register(issuer.eth_account, encrypted_info). \
        transact({'from': invoker_address, 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)
    print("register_personalinfo:" + str(PersonalInfoContract.functions.isRegistered(invoker_address, issuer.eth_account).call()))


# 収納代行業者をPaymentGatewayに登録
def add_agent_to_payment_gateway(agent_address, issuer):
    PaymentGatewayContract = ContractUtils.get_contract('PaymentGateway', issuer.payment_gateway_contract_address)
    tx = PaymentGatewayContract.functions.addAgent(agent_address). \
        buildTransaction({'from': issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
    ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)


# 決済用銀行口座情報登録（認可まで）
def register_payment_account(invoker_address, invoker_password, encrypted_info, agent_address, issuer):
    PaymentGatewayContract = ContractUtils.get_contract('PaymentGateway', issuer.payment_gateway_contract_address)

    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, invoker_password)

    tx_hash = PaymentGatewayContract.functions.register(agent_address, encrypted_info). \
        transact({'from': invoker_address, 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)

    # 2) 認可 from Agent
    web3.eth.defaultAccount = agent_address
    web3.personal.unlockAccount(agent_address, 'password', 10000)

    tx_hash = PaymentGatewayContract.functions.approve(invoker_address). \
        transact({'from': agent_address, 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)
    print("register PaymentGatewayContract:" + str(PaymentGatewayContract.functions.accountApproved(invoker_address, agent_address).call()))


def main(data_count, issuer):
    token_type = 'IbetCoupon'

    # 収納代行業者（Agent）のアドレス作成 -> PaymentAccountの登録
    agent_address = web3.personal.newAccount('password')
    eth_account_password = fernet.decrypt(issuer.encrypted_account_password.encode()).decode()
    register_payment_account(issuer.eth_account, eth_account_password, issuer_encrypted_info, agent_address, issuer)
    print("agent_address: " + agent_address)

    # 収納代行業者をPaymentGatewayに追加
    add_agent_to_payment_gateway(agent_address, issuer)

    # クーポンDEX情報を取得
    exchange_address = issuer.ibet_coupon_exchange_contract_address
    ExchangeContract = ContractUtils.get_contract('IbetCouponExchange', exchange_address)
    print("exchange_address: " + exchange_address)

    # トークン発行 -> 売出
    token_dict = issue_token(exchange_address, data_count, token_type, issuer)
    register_token_list(token_dict, token_type, issuer)
    offer_token(agent_address, exchange_address, token_dict, data_count, token_type, ExchangeContract, issuer)
    order_id = get_latest_orderid(ExchangeContract)
    print("token_address: " + token_dict['address'])
    print("order_id: " + str(order_id))

    # 投資家アドレスの作成
    trader_address = web3.personal.newAccount('password')
    register_personalinfo(trader_address, trader_encrypted_info, issuer)
    register_payment_account(trader_address, 'password', trader_encrypted_info, agent_address, issuer)

    # 約定を入れる(全部買う)：投資家
    buy_coupon_token(trader_address, ExchangeContract, order_id, data_count)
    agreement_id = get_latest_agreement_id(ExchangeContract, order_id)

    # 決済承認：収納代行
    web3.eth.defaultAccount = agent_address
    web3.personal.unlockAccount(agent_address, 'password', 10000)
    ExchangeContract.functions.confirmAgreement(order_id, agreement_id).transact(
        {'from': agent_address, 'gas': Config.TX_GAS_LIMIT}
    )

    # クーポンの消費
    TokenContract = ContractUtils.get_contract(token_type, token_dict['address'])
    for count in range(0, data_count):
        web3.eth.defaultAccount = trader_address
        web3.personal.unlockAccount(trader_address, 'password', 10000)
        tx_hash = TokenContract.functions.consume(1).transact(
            {'from': trader_address, 'gas': Config.TX_GAS_LIMIT}
        )
        web3.eth.waitForTransactionReceipt(tx_hash)
        print("count: " + str(count))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="クーポン利用履歴の登録")
    parser.add_argument("data_count", type=int, help="登録件数")
    parser.add_argument("--issuer", '-s', type=str, help="発行体アドレス")
    args = parser.parse_args()

    if not args.data_count:
        raise Exception("登録件数が必要")

    issuer_address = args.issuer if args.issuer is not None else web3.eth.accounts[0]
    issuer_model = db_session.query(Issuer).filter(Issuer.eth_account == issuer_address).first()
    if issuer_model is None:
        raise Exception("発行体が未登録です")
    print(f'発行体アドレス: {issuer_model.eth_account}')

    main(args.data_count, issuer_model)
