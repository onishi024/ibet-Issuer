# -*- coding: utf-8 -*-
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

WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# DB
URI = os.environ.get("DATABASE_URL") or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

fernet = Fernet(os.environ['ETH_ACCOUNT_PASSWORD_SECRET_KEY'].encode())


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
        buildTransaction({'from': issuer.eth_account, 'gas': 4000000})
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
        buildTransaction({'from': issuer.eth_account, 'gas': 4000000})
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
        transact({'from': trader_address, 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)


# 株主名簿用個人情報登録
def register_personalinfo(invoker_address, encrypted_info, issuer):
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, 'password')
    PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', issuer.personal_info_contract_address)

    tx_hash = PersonalInfoContract.functions.register(issuer.eth_account, encrypted_info). \
        transact({'from': invoker_address, 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)
    print("register_personalinfo:" + str(PersonalInfoContract.functions.isRegistered(invoker_address, issuer.eth_account).call()))


# 収納代行業者をPaymentGatewayに登録
def add_agent_to_payment_gateway(agent_address, issuer):
    PaymentGatewayContract = ContractUtils.get_contract('PaymentGateway', issuer.payment_gateway_contract_address)
    tx = PaymentGatewayContract.functions.addAgent(agent_address). \
        buildTransaction({'from': issuer.eth_account, 'gas': 4000000})
    ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)


# 決済用銀行口座情報登録（認可まで）
def register_payment_account(invoker_address, invoker_password, encrypted_info, agent_address, issuer):
    PaymentGatewayContract = ContractUtils.get_contract('PaymentGateway', issuer.payment_gateway_contract_address)

    # 1) 登録 from Invoker
    web3.eth.defaultAccount = invoker_address
    web3.personal.unlockAccount(invoker_address, invoker_password)

    tx_hash = PaymentGatewayContract.functions.register(agent_address, encrypted_info). \
        transact({'from': invoker_address, 'gas': 4000000})
    web3.eth.waitForTransactionReceipt(tx_hash)

    # 2) 認可 from Agent
    web3.eth.defaultAccount = agent_address
    web3.personal.unlockAccount(agent_address, 'password', 10000)

    tx_hash = PaymentGatewayContract.functions.approve(invoker_address). \
        transact({'from': agent_address, 'gas': 4000000})
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
            {'from': trader_address, 'gas': 400000}
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
