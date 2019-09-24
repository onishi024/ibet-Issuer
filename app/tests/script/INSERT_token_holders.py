# -*- coding: utf-8 -*-
import os
import json
import base64
import argparse
import time
import sys

path = os.path.join(os.path.dirname(__file__), "../../..")
sys.path.append(path)

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address
from app.contracts import Contract

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from app.models import Token
from config import Config

# personal_info_json = {
#     "name":"株式会社１",
#     "address":{
#         "postal_code":"1234567",
#         "prefecture":"東京都",
#         "city":"中央区",
#         "address1":"日本橋11-1",
#         "address2":"東京マンション１０１"
#     }
# }
issuer_encrypted_info = 'C3xjipCzPIbgydw0cObtsxadHqU3GuXd1u89EJuxMpyfnEJZ7CSXKrr4jF55Cji94xgknLjm7zFKfUzLcySXu5rj6mlJCfdKozBQ1GM7iN1wt+toXmiqCcGy0Rozis39oaykKT/s5CQtIQIbOf8DnQBGW7YP1bPx/yj5bEFUCf6+6QQHsmh4UTIugiQoyFms/ffNZjgnea49ja/eyyxt3mc/4tSoxHqamyQtvZ2UxVeMFHZ4QbbSomKXEwi7wp95rHzjnjgTvjxjHUFyMUhOTd+Y581uX2VnFCVb9ddYXrUOu7yySguLSCugr7ihNQUEe12im10XLDyksA+uCJnp0hSBBKCJ8oarbLYYuPfcZrP5YsfIZGJp5xpcqvmq795iOLqZQrhL4gfJXJ3JD+6KuCEX2gk3w8KWU6vS65yVhU5RxOtIJXuGiw/vzhdA2ZtI0hGA4JwG5o+iRBXuxeRz4uqucMHYj2VUu/2QFmtsO/4IqurDEQTLK+brPHnmzpdKPOvSQ4pkbrOgDkKOkXjsuFVf+eJEhjuiXr0CM9Y4yyKv6YMtVlsISG+yyKduMwXluPwbJUISMpz7P9y+WpvVQ1vrCqq/thxMrAzpGqj0ZYIrfuuWASpYGxH/xkYp24paXbLeYT4GJuPvT0RdpXcGCLBmZ8NT2VyePGXIdbmF4zKF+g9lGKzz/vRiSakIbHLK7hC1xTwHg4mrf2r1PBft3W4DyIll6eU7N5rdb8P4SlzM0dlfVrK5x4VP7VmRdsWvu8FBCHqTIlVBODbBT60MVsB0b/qEX3h3CBREUmwhWEYXShG12SNuO1rR/anEz+yv/DlVrfMthejBglNd76bUraouPgNrqI3gGRP+E6AP9/W5JJFQdteA/Hbkj9vI6A3l/UALNmLBGypOhO7cMPYiDkl5KIO2p53XpN6xRJtq3lXArkXD7wNn/I7zs3bj9U//bEE/qLngPMJFqNSWb+owGwx8vHKhZlozpVf/tWFG2nKrIvNCC1XtYH/G2rs/7HCVvvRksgOtJ+LOyXui/xtL4i1RMQh0AmwofwnnIL4zKXjX/b4Tog/D2nxr6ifG2baWE46h9WRdyV9ICzW+NRD3AQObkRb7e3LThMy7pupbPESGiO/kQfDFEFoNw47YD80COFU/0Ih8ylLtumk/ecunn8ayLyWhX6qHpdIR1ILYOPv5jbMcOWAs5FQfBVJlDv3iJNQrz3nN30/GecMS5unfVe05pknuvSIs2L6qLWgK4b3DyyZrbkvacNAzGC5GDt9jG107FsvtATlRt9KaxivjGsZpJ67//lkC3l+MJFUkMFL/tzNP7PGRhj801LggtzV+jjBG7EuDUP2K/pAQ4kVE4s3mIM61N3ytnvdcL3gTnjTlp5S6gb0taM/9hJTsAUWjycE0LqVdPhrYTvEvChN39eXstkU8WGI2V1iLXB4XKiTXmLqUXDtx7Yc5bvUiSaMXlxa8wMoeh/qmTcOvBbGSSzaTzc1r47f8LcNRLhLt3zogiI/pdiehDdEOG9u4eQNptU5ePCZcQcVZak7QbcIxECOvz4FZb8cR2JTDm01RnvyMyu2miB4ambWnRMiI9I30lPWgBlyvkGv3oCEIP+/P8Jy3wRRkMgbyUPStLTAQUeQ2JMXrQHLdgOLOEfvzBn9aZRuagzhdcdtaeePXFe1JbEc0worY6rHPNInTPejuV+Y='
# personal_info_json = {
#     "name":"ﾀﾝﾀｲﾃｽﾄ",
#     "address":{
#         "postal_code":"1040053",
#         "prefecture":"東京都",
#         "city":"中央区",
#         "address1":"勝どき6丁目３－２",
#         "address2":"ＴＴＴ６０１２"
#     }
# }
trader_encrypted_info = 'oR3oSAdy1m6MR2nYKTsccjxdXlgLDx2MJZEir5qKpb9hpHEWisOn79GE8+o1ThG/BCzirZjx9z3gc40PmM+1l2VH+6c5ouSWkZ3JhoT4SUsf9YTAurj6jySzTcPkCMC9VPP+Nm4+XJyt3QroPzDOsJKaGycn63/B8BLTV6zZaDi9ZDBtZL0A1xMEx2aQJsXCj+cn6fGFy7VV8NG1+WYyUDZmXTK8nzR75J2onsiT4FzwtSCzZbM4/qME4O0rOlnaqjBoyn6Ae46S6LO72JPskT/b5pWM+mH8+/buLdGaxO3D1k6ICTvjNJaO7gxTNTsm3tWGotp9tzzkDsxYcVE+qr4/ufmsE6Qn3/pI1DtEZbMyXu51ucn7JYyQNiPN99OXbkTs2/DHsy7RtvujS+PXH4KHjH0//NbdyUxgEmGbf3XvZ2yDDRUKpi5jHs82mtECGPWN9hKzlwkV7UXp/BBHZP+MsyiU1pZCkqIGIrt9WlE/v9TlJXzarcJmqWL6LmG2b5g6ublux/AaYyYXjwNyKbP0kQJGYoGNV4KODNEQd6DNc5uI24laJd8GY7ucDcB2F/j1y1S5vWIQIOM9ksSr9K0xfsaiqGpNWtbquYrOv3lNVozFx22C8hTWDyMOCmkTEcha2nTnLUvSsopZeNlAfRxnNdqjtHqp8iBAqVlpxRpIgCjk9QTf1lYmNK3jb2/4Cyt8xAo0Z4ty6qOzeEcwd+BjGMbfWdxtGSJHDidr7nP56MOGKSzwOnLxLVYVL8YuV6MnzqDtbts/Vbw9mkX5zwddIfvsGlNvhbrDR8WSrXRVeWiwnbXnhc4njpsRLRlCXwvHVbhXzdUvEyfXmMdMGRScVBLLeb0BQK9Aea1ZuwKsK19JhK5QUrnYeimMRzJ/YUX5mMlJ4Skek7Lkn8py5hX3rZ3/SvLEXKe2GxkvqTPbwnyS+ZNAvGpyRl8AIthOHucW4Fnjl8KQpqS2GMJpj+SJRq8/HCpaR50743S5j6Ha0gx3D3/R032an+cgg7a875BNX0hgldffzoDr6+nHEtwsY/J96rkUFmeubmsISu0wAxH6C7XTsCFs90awBwIAydOgmbOovUub/yz/CJhbgbMrAMv1Mv2wnLIt0av8nC359AuRanIGr7q/ynDYqUS9mdUlpyfVbwWPJm0hMFfuJxdvVVHnyr2jg2GqtgvE8QcN18l1aI1FJDfqa7W7grlwn9+EQo+JXE1Xd7YZdeJNtKSD4aIQAFnIoIM3A7fkoPAS4sc+PdUzA3UNgomByNP3/cdcs/L3cvEpDjlTNzFLcQ2yojEXolcg2SZzpmb7MV3E5RQLnjOL+u/frwqk15up7jNiqfNp7N/o/wmjf6m+ceJq7b03o2oNLE+Ng6lNqLWNduII4Lq0N6qOgWJ/02LF1X/9oeBDPuPiLUZGkyy5y3FCuY4KN/hDUUpxGsxBOYfn+oFepAu6bz4UpxgaEu23DyCeKnkBlQITi1kSl7F7WHv1XBHF53eEY4fs4n0ZrOYWOzEFt/NfKm/oxiyIdSsCfGTcgmC/DGC90vM4sPPRXa7x7Xd8xJRbTnEuA88ALzCSeMt1NyNNtSKpw9xv+UIyFMkuDYsOoNRrdThZ/KvjYSMsAvNBXG0x6AYMz4x9oZ25VBiy/yWbivbN2nFPlWM7xyaQWMlTBVZZdCgnOoOR1tby7IAwlzTd1oGm+DJx9hA='

# issuerのweb3
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER')
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
ETH_ACCOUNT = to_checksum_address(web3.eth.accounts[0])
ETH_ACCOUNT_PASSWORD = os.environ.get('ETH_ACCOUNT_PASSWORD')

# agentのweb3
WEB3_HTTP_PROVIDER_AGENT = os.environ.get('WEB3_HTTP_PROVIDER_AGENT')
web3_agent = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER_AGENT))
web3_agent.middleware_stack.inject(geth_poa_middleware, layer=0)
AGENT_ACCOUNT = to_checksum_address(web3_agent.eth.accounts[0])
AGENT_ACCOUNT_PASSWORD = os.environ.get('AGENT_ACCOUNT_PASSWORD')

# agent用コントラクト取得
def get_agent_contract(contract_name, address):
    contracts = json.load(open('data/contracts.json' , 'r'))
    contract = web3_agent.eth.contract(
        address = to_checksum_address(address),
        abi = contracts[contract_name]['abi'],
    )
    return contract

# コントラクト
TOKEN_LIST_CONTRACT_ADDRESS = to_checksum_address(os.environ.get('TOKEN_LIST_CONTRACT_ADDRESS'))
PERSONAL_INFO_CONTRACT_ADDRESS = to_checksum_address(os.environ.get('PERSONAL_INFO_CONTRACT_ADDRESS'))
PAYMENT_GATEWAY_CONTRACT_ADDRESS = to_checksum_address(os.environ.get('PAYMENT_GATEWAY_CONTRACT_ADDRESS'))
PaymentGatewayContract = Contract.get_contract('PaymentGateway', PAYMENT_GATEWAY_CONTRACT_ADDRESS)
PaymentGatewayContractAgent = get_agent_contract('PaymentGateway', PAYMENT_GATEWAY_CONTRACT_ADDRESS)
IBET_SB_EXCHANGE_CONTRACT_ADDRESS = \
    to_checksum_address(os.environ.get('IBET_SB_EXCHANGE_CONTRACT_ADDRESS'))
IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = \
    to_checksum_address(os.environ.get('IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS'))
IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = \
    to_checksum_address(os.environ.get('IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS'))

# DB
URI = os.environ.get("DATABASE_URL") or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

# トークン発行
def issue_token(exchange_address, data_count, token_type):
    attribute = {}
    attribute['name'] = 'SEINO_TEST_TOKEN_HOLDER_' + str(data_count)
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
            attribute['contactInformation'], attribute['privacyPolicy']
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

    web3.eth.defaultAccount = ETH_ACCOUNT
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD)
    _, bytecode, bytecode_runtime = Contract.get_contract_info(token_type)
    contract_address, abi, tx_hash  = Contract.deploy_contract(token_type, arguments, ETH_ACCOUNT)

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

# トークン売出(売り)
def offer_token(invoker_address, invoker_password, exchange_address, token_dict, amount, token_type, ExchangeContract):
    transfer_to_exchange(invoker_address, invoker_password, exchange_address, token_dict, amount, token_type)
    make_sell_token(invoker_address, invoker_password, exchange_address, token_dict, amount, ExchangeContract)

# 取引コントラクトにトークンをチャージ
def transfer_to_exchange(invoker_address, invoker_password, exchange_address, token_dict, amount, token_type):
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, invoker_password)
    TokenContract = Contract.get_contract(token_type, token_dict['address'])
    tx_hash = TokenContract.functions.transfer(exchange_address, amount).\
        transact({'from':invoker_address, 'gas':4000000})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)
    print("transfer_to_exchange:balanceOf exchange_address:" + str(TokenContract.functions.balanceOf(exchange_address).call()))

# トークンの売りMake注文
def make_sell_token(invoker_address, invoker_password, exchange_address, token_dict, amount, ExchangeContract):
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, invoker_password)
    gas = ExchangeContract.estimateGas().\
        createOrder(token_dict['address'], amount, 100, False, AGENT_ACCOUNT)
    tx_hash = ExchangeContract.functions.\
        createOrder(token_dict['address'], amount, 100, False, AGENT_ACCOUNT).\
        transact({'from':invoker_address, 'gas':gas})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)

# 直近注文IDを取得
def get_latest_orderid(ExchangeContract):
    latest_orderid = ExchangeContract.functions.latestOrderId().call()
    return latest_orderid

# トークンの買いTake注文
def buy_bond_token(trader_address, ExchangeContract, order_id, amount):
    web3.eth.defaultAccount = trader_address
    web3.personal.unlockAccount(trader_address, 'password')
    tx_hash = ExchangeContract.functions.\
        executeOrder(order_id, amount, True).\
        transact({'from':trader_address, 'gas':4000000})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)

# 株主名簿用個人情報登録
def register_personalinfo(invoker_address, encrypted_info):
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, 'password')
    PersonalInfoContract = Contract.get_contract('PersonalInfo', PERSONAL_INFO_CONTRACT_ADDRESS)

    tx_hash = PersonalInfoContract.functions.register(ETH_ACCOUNT, encrypted_info).\
        transact({'from':invoker_address, 'gas':4000000})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)
    print("register_personalinfo:" + str(PersonalInfoContract.functions.isRegistered(invoker_address, ETH_ACCOUNT).call()))

# 決済用銀行口座情報登録（認可まで）
def register_payment_account(invoker_address, invoker_password, encrypted_info):
    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, invoker_password)

    tx_hash = PaymentGatewayContract.functions.register(AGENT_ACCOUNT, encrypted_info).\
        transact({'from':invoker_address, 'gas':4000000})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)

    # 2) 認可 from Agent
    web3_agent.eth.defaultAccount = AGENT_ACCOUNT
    web3_agent.personal.unlockAccount(AGENT_ACCOUNT, AGENT_ACCOUNT_PASSWORD, 10000)

    tx_hash = PaymentGatewayContractAgent.functions.approve(invoker_address).\
        transact({'from':AGENT_ACCOUNT, 'gas':4000000})
    tx = web3.eth.waitForTransactionReceipt(tx_hash)
    print("register PaymentGatewayContract:" + str(PaymentGatewayContract.functions.accountApproved(invoker_address, AGENT_ACCOUNT).call()))

def main(data_count, token_type, secondary_sell_flag):
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 10000)
    if token_type == 'IbetStraightBond':
        ExchangeContract = Contract.get_contract('IbetStraightBondExchange', IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
        ExchangeContractAgent = get_agent_contract('IbetStraightBondExchange', IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
        exchange_address = IBET_SB_EXCHANGE_CONTRACT_ADDRESS
    elif token_type == 'IbetMembership':
        ExchangeContract = Contract.get_contract('IbetMembershipExchange', IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS)
        ExchangeContractAgent = get_agent_contract('IbetMembershipExchange', IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS)
        exchange_address = IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
    elif token_type == 'IbetCoupon':
        ExchangeContract = Contract.get_contract('IbetCouponExchange', IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS)
        ExchangeContractAgent = get_agent_contract('IbetCouponExchange', IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS)
        exchange_address = IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    print("exchange_address: " + exchange_address)
    print("agent_address: " + AGENT_ACCOUNT)
    # トークン発行
    token_dict = issue_token(exchange_address, data_count, token_type)
    # トークンリストに登録
    register_token_list(token_dict, token_type)
    # 売出
    offer_token(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, exchange_address, token_dict, data_count, token_type, ExchangeContract)
    # orderID取得
    order_id = get_latest_orderid(ExchangeContract)
    print("token_address: " + token_dict['address'])
    print("order_id: " + str(order_id))
    # 約定を入れる
    for agreement_id in range(0, data_count):
        # 投資家アドレスの作成
        trader_address = web3.personal.newAccount('password')
        register_personalinfo(trader_address, trader_encrypted_info)
        register_payment_account(trader_address, 'password', trader_encrypted_info)
        # 決済を入れる
        buy_bond_token(trader_address, ExchangeContract, order_id, 1)
        # 決済の承認
        web3_agent.eth.defaultAccount = AGENT_ACCOUNT
        web3_agent.personal.unlockAccount(AGENT_ACCOUNT, AGENT_ACCOUNT_PASSWORD, 10000)
        tx_hash = ExchangeContractAgent.functions.confirmAgreement(order_id, agreement_id).transact(
            {'from':AGENT_ACCOUNT, 'gas':400000}
        )
        tx = web3.eth.waitForTransactionReceipt(tx_hash)
        if secondary_sell_flag == "1":
            offer_token(trader_address, 'password', exchange_address, token_dict, 1, token_type, ExchangeContract)

        print("agreement_id: " + str(agreement_id))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="tokenホルダーの登録")
    parser.add_argument("data_count", type=int, help="登録件数")
    parser.add_argument("token_type", type=str, help="IbetStraightBond, IbetMembership, IbetCoupon")
    parser.add_argument("secondary_sell_flag", type=str, help="0:売らない, 1:投資家が売り注文を出す")
    args = parser.parse_args()

    if not args.data_count:
        raise Exception("登録件数が必要")

    if not args.token_type:
        raise Exception("IbetStraightBond, IbetMembership, IbetCoupon")

    if not args.secondary_sell_flag:
        raise Exception("0:売らない, 1:投資家が売り注文を出す")

    main(args.data_count, args.token_type, args.secondary_sell_flag)