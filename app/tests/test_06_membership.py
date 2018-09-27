# -*- coding:utf-8 -*-
import pytest
import os
import time

from .conftest import TestBase
from .account_config import eth_account
from config import Config
from .contract_modules import *
from ..models import Token
from app.contracts import Contract

from logging import getLogger
logger = getLogger('api')

class TestCoupon(TestBase):
    # personal_info_json = {
    #     "name":"株式会社１",
    #     "address":{
    #         "postal_code":"1234567",
    #         "prefecture":"東京都",
    #         "city":"中央区",
    #         "address1":"日本橋11-1",
    #         "address2":"東京マンション１０１"
    #     },
    #     "bank_account":{
    #         "bank_name": "三菱UFJ銀行",
    #         "bank_code": "0005",
    #         "branch_office": "東恵比寿支店",
    #         "branch_code": "610",
    #         "account_type": 1,
    #         "account_number": "1234567",
    #         "account_holder": "ｶﾌﾞｼｷｶﾞｲｼﾔｹﾂｻｲﾀﾞｲｺｳ"
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
    #     },
    #     "bank_account":{
    #         "bank_name": "みずほ銀行",
    #         "bank_code": "0001",
    #         "branch_office": "日本橋支店",
    #         "branch_code": "101",
    #         "account_type": 2,
    #         "account_number": "7654321",
    #         "account_holder": "ﾀﾝﾀｲﾃｽﾄｺｳｻﾞ"
    #     }
    # }
    trader_encrypted_info = 'oR3oSAdy1m6MR2nYKTsccjxdXlgLDx2MJZEir5qKpb9hpHEWisOn79GE8+o1ThG/BCzirZjx9z3gc40PmM+1l2VH+6c5ouSWkZ3JhoT4SUsf9YTAurj6jySzTcPkCMC9VPP+Nm4+XJyt3QroPzDOsJKaGycn63/B8BLTV6zZaDi9ZDBtZL0A1xMEx2aQJsXCj+cn6fGFy7VV8NG1+WYyUDZmXTK8nzR75J2onsiT4FzwtSCzZbM4/qME4O0rOlnaqjBoyn6Ae46S6LO72JPskT/b5pWM+mH8+/buLdGaxO3D1k6ICTvjNJaO7gxTNTsm3tWGotp9tzzkDsxYcVE+qr4/ufmsE6Qn3/pI1DtEZbMyXu51ucn7JYyQNiPN99OXbkTs2/DHsy7RtvujS+PXH4KHjH0//NbdyUxgEmGbf3XvZ2yDDRUKpi5jHs82mtECGPWN9hKzlwkV7UXp/BBHZP+MsyiU1pZCkqIGIrt9WlE/v9TlJXzarcJmqWL6LmG2b5g6ublux/AaYyYXjwNyKbP0kQJGYoGNV4KODNEQd6DNc5uI24laJd8GY7ucDcB2F/j1y1S5vWIQIOM9ksSr9K0xfsaiqGpNWtbquYrOv3lNVozFx22C8hTWDyMOCmkTEcha2nTnLUvSsopZeNlAfRxnNdqjtHqp8iBAqVlpxRpIgCjk9QTf1lYmNK3jb2/4Cyt8xAo0Z4ty6qOzeEcwd+BjGMbfWdxtGSJHDidr7nP56MOGKSzwOnLxLVYVL8YuV6MnzqDtbts/Vbw9mkX5zwddIfvsGlNvhbrDR8WSrXRVeWiwnbXnhc4njpsRLRlCXwvHVbhXzdUvEyfXmMdMGRScVBLLeb0BQK9Aea1ZuwKsK19JhK5QUrnYeimMRzJ/YUX5mMlJ4Skek7Lkn8py5hX3rZ3/SvLEXKe2GxkvqTPbwnyS+ZNAvGpyRl8AIthOHucW4Fnjl8KQpqS2GMJpj+SJRq8/HCpaR50743S5j6Ha0gx3D3/R032an+cgg7a875BNX0hgldffzoDr6+nHEtwsY/J96rkUFmeubmsISu0wAxH6C7XTsCFs90awBwIAydOgmbOovUub/yz/CJhbgbMrAMv1Mv2wnLIt0av8nC359AuRanIGr7q/ynDYqUS9mdUlpyfVbwWPJm0hMFfuJxdvVVHnyr2jg2GqtgvE8QcN18l1aI1FJDfqa7W7grlwn9+EQo+JXE1Xd7YZdeJNtKSD4aIQAFnIoIM3A7fkoPAS4sc+PdUzA3UNgomByNP3/cdcs/L3cvEpDjlTNzFLcQ2yojEXolcg2SZzpmb7MV3E5RQLnjOL+u/frwqk15up7jNiqfNp7N/o/wmjf6m+ceJq7b03o2oNLE+Ng6lNqLWNduII4Lq0N6qOgWJ/02LF1X/9oeBDPuPiLUZGkyy5y3FCuY4KN/hDUUpxGsxBOYfn+oFepAu6bz4UpxgaEu23DyCeKnkBlQITi1kSl7F7WHv1XBHF53eEY4fs4n0ZrOYWOzEFt/NfKm/oxiyIdSsCfGTcgmC/DGC90vM4sPPRXa7x7Xd8xJRbTnEuA88ALzCSeMt1NyNNtSKpw9xv+UIyFMkuDYsOoNRrdThZ/KvjYSMsAvNBXG0x6AYMz4x9oZ25VBiy/yWbivbN2nFPlWM7xyaQWMlTBVZZdCgnOoOR1tby7IAwlzTd1oGm+DJx9hA='

    # ＜正常系1＞
    # 一覧の参照(0件)
    def test_normal_1(self, app, shared_contract):
        # Config設定は1_1で全て実施
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.WHITE_LIST_CONTRACT_ADDRESS = shared_contract['WhiteList']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetMembershipExchange']['address']

        # whitelist登録
        register_terms(eth_account['agent'], shared_contract['WhiteList'])
        register_whitelist(eth_account['issuer'], shared_contract['WhiteList'], self.issuer_encrypted_info)

        # 会員権発行
        attribute = {
            'name': 'テスト債券',
            'symbol': 'BOND',
            'totalSupply': 1000000,
            'details': '',
            'returnDetails': '',
            'expirationDate': '',
            'memo': '',
            'transferable': True
        }
        arguments = [
            attribute['name'], attribute['symbol'], attribute['totalSupply'],
            attribute['details'], attribute['returnDetails'],
            attribute['expirationDate'], attribute['memo'],
            attribute['transferable']
        ]
        web3.eth.defaultAccount = eth_account['issuer']['account_address']
        web3.personal.unlockAccount(eth_account['issuer']['account_address'],
                                    eth_account['issuer']['password'])
        membership_contract_address, membership_abi, _ = Contract.deploy_contract('IbetMembership',
         arguments, eth_account['issuer']['account_address'])

        # 売り注文
        amount = 100
        price = 10
        
        TokenContract = Contract.get_contract('IbetMembership', membership_contract_address)

        totalSupply = TokenContract.functions.totalSupply().call()
        logger.info("totalSupply: " + totalSupply)
        balances_membership = TokenContract.functions.balances(eth_account['issuer']['account_address']).call()
        logger.info("balances_membership: " +　balances_membership)

        # transfer
        tx_hash = TokenContract.functions.transfer(shared_contract['IbetMembershipExchange']['address'], amount).\
            transact({'from':eth_account['issuer']['account_address'], 'gas':4000000})
        tx = web3.eth.waitForTransactionReceipt(tx_hash)

        balances_membership = TokenContract.functions.balances(eth_account['issuer']['account_address']).call()
        logger.info("balances_membership: " + balances_membership)

        ExchangeContract = Contract.get_contract('IbetMembershipExchange',
         shared_contract['IbetMembershipExchange']['address'])

        balances_ex = ExchangeContract.functions.balances(eth_account['issuer']['account_address'], 
            membership_contract_address).call()
        logger.info("balances_ex: " + balances_ex)


        gas = ExchangeContract.estimateGas().\
            createOrder(membership_contract_address, amount, price, False, eth_account['agent']['account_address'])
        tx_hash = ExchangeContract.functions.\
            createOrder(membership_contract_address, amount, price, False, eth_account['agent']['account_address']).\
            transact({'from':eth_account['issuer']['account_address'], 'gas':gas})
        tx = web3.eth.waitForTransactionReceipt(tx_hash)

        latest_orderid = ExchangeContract.functions.latestOrderId().call() - 1

        logger.info("latest_orderid: " + latest_orderid)
        assert latest_orderid == 0

        # 買い注文
        web3.eth.defaultAccount = eth_account['trader']['account_address']
        web3.personal.unlockAccount(eth_account['trader']['account_address'],
                                    eth_account['trader']['password'])

        tx_hash = ExchangeContract.functions.\
            executeOrder(latest_orderid, amount, True).\
            transact({'from':eth_account['trader']['account_address'], 'gas':4000000})
        tx = web3.eth.waitForTransactionReceipt(tx_hash)

        # 購入できてないこと(発行体のexのバランスがamount))
        balances_ex = ExchangeContract.functions.balances(eth_account['issuer']['account_address'], 
            membership_contract_address).call()
        logger.info("balances_ex: " + balances_ex)
        assert balances_ex == amount

        # 投資家のバランス 0 
        balances_trader = TokenContract.functions.balances(eth_account['trader']['account_address']).call()
        logger.info("balances_trader")
        logger.info(balances_trader)
        logger.info("balances_trader-----------")
        assert balances_trader == 0

        # whitelist登録し、再度買う。
        register_whitelist(eth_account['trader'], shared_contract['WhiteList'], self.issuer_encrypted_info)
        web3.eth.defaultAccount = eth_account['trader']['account_address']
        web3.personal.unlockAccount(eth_account['trader']['account_address'],
                                    eth_account['trader']['password'])

        tx_hash = ExchangeContract.functions.\
            executeOrder(latest_orderid, amount, True).\
            transact({'from':eth_account['trader']['account_address'], 'gas':4000000})
        tx = web3.eth.waitForTransactionReceipt(tx_hash)

        # 購入できていること(発行体のexのバランスが0))
        balances_ex = ExchangeContract.functions.balances(eth_account['issuer']['account_address'], 
            membership_contract_address).call()
        logger.info("balances_ex")
        logger.info(balances_ex)
        logger.info("balances_ex-----------")
        assert balances_ex == 0

        # 投資家のバランス amount 
        balances_trader = TokenContract.functions.balances(eth_account['trader']['account_address']).call()
        logger.info("balances_trader")
        logger.info(balances_trader)
        logger.info("balances_trader-----------")
        assert balances_trader == amount
