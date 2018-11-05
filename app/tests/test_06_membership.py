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

class TestMembership(TestBase):
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

    ##################
    # URL
    ##################
    url_list = 'membership/list'
    url_positions = 'membership/positions'
    url_issue = 'membership/issue'
    url_setting = 'membership/setting/'
    url_sell = 'membership/sell/'
    url_cancel_order = 'membership/cancel_order/'
    url_release = 'membership/release'
    url_invalid = 'membership/invalid'
    url_valid = 'membership/valid'
    url_add_supply = 'membership/add_supply/'
    url_holders = 'membership/holders/'
    url_holder = 'membership/holder/'
    ##################
    # 会員権Data
    ##################
    token_data1 = {
        'name': 'テスト会員権',
        'symbol': 'KAIINKEN',
        'totalSupply': 1000000,
        'details': 'details',
        'returnDetails': 'returnDetails',
        'expirationDate': '20191231',
        'memo': 'memo',
        'transferable': 'True',
        'image_small': 'image_small',
        'image_medium': 'image_medium',
        'image_large': 'image_large'
    }
    # imageなし, transferable:False
    token_data2 = {
        'name': '2件目会員権',
        'symbol': '2KENME',
        'totalSupply': 2000000,
        'details': '2details',
        'returnDetails': '2returnDetails',
        'expirationDate': '20201231',
        'memo': '2memo',
        'transferable': 'False',
        'image_small': '',
        'image_medium': '',
        'image_large': ''
    }
    # 設定画面での編集用
    token_data3 = {
        'name': 'テスト会員権',
        'symbol': 'KAIINKEN',
        'totalSupply': 1000000,
        'details': '3details',
        'returnDetails': '3returnDetails',
        'expirationDate': '20211231',
        'memo': '3memo',
        'transferable': 'False',
        'image_small': '3image_small',
        'image_medium': '3image_medium',
        'image_large': '3image_large'
    }

    # ＜正常系1_1＞
    # ＜会員権の0件確認＞
    # 会員権一覧の参照(0件)
    def test_normal_1_1(self, app, shared_contract):
        # Config設定は1_1で全て実施
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetMembershipExchange']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        # 一覧
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>会員権一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜会員権の0件確認＞
    # 募集管理(0件)
    def test_normal_1_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2_1＞
    # ＜会員権の1件確認＞
    # 新規発行　→　DB登録処理 →　詳細画面
    def test_normal_2_1(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data=self.token_data1
        )
        assert response.status_code == 302

        # 2秒待機
        time.sleep(2)

        # DB登録処理
        processorIssueEvent(db)

        # 設定画面
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply']).encode('utf-8') in response.data
        assert self.token_data1['details'].encode('utf-8') in response.data
        assert self.token_data1['returnDetails'].encode('utf-8') in response.data
        assert self.token_data1['expirationDate'].encode('utf-8') in response.data
        assert self.token_data1['memo'].encode('utf-8') in response.data
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data
        assert self.token_data1['image_small'].encode('utf-8') in response.data
        assert self.token_data1['image_medium'].encode('utf-8') in response.data
        assert self.token_data1['image_large'].encode('utf-8') in response.data

    # ＜正常系2_2＞
    # ＜会員権の1件確認＞
    # 会員権一覧の参照(1件)
    def test_normal_2_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>会員権一覧'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系2_3＞
    # ＜会員権の1件確認＞
    # 募集管理(1件)
    def test_normal_2_3(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '<td>1000000</td>\n            <td>1000000</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系3_1＞
    # ＜会員権一覧（複数件）＞
    # 新規発行（画像URLなし）
    def test_normal_3_1(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data=self.token_data2
        )
        assert response.status_code == 302

        # 2秒待機
        time.sleep(2)

        # DB登録処理
        processorIssueEvent(db)

        # 設定画面
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[1]
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert str(self.token_data2['totalSupply']).encode('utf-8') in response.data
        assert self.token_data2['details'].encode('utf-8') in response.data
        assert self.token_data2['returnDetails'].encode('utf-8') in response.data
        assert self.token_data2['expirationDate'].encode('utf-8') in response.data
        assert self.token_data2['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data2['image_small'].encode('utf-8') in response.data
        assert self.token_data2['image_medium'].encode('utf-8') in response.data
        assert self.token_data2['image_large'].encode('utf-8') in response.data

    # ＜正常系3_2＞
    # ＜会員権一覧（複数件）＞
    # 会員権一覧（複数件）
    def test_normal_3_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token1 = tokens[0]
        token2 = tokens[1]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>会員権一覧'.encode('utf-8') in response.data
        # 1
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token1.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data
        # 2
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert token2.token_address.encode('utf-8') in response.data

    # ＜正常系3_3＞
    # ＜会員権一覧（複数件）＞
    # 募集管理（複数件）
    def test_normal_3_3(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token1 = tokens[0]
        token2 = tokens[1]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        # 1
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token1.token_address.encode('utf-8') in response.data
        assert '<td>1000000</td>\n            <td>1000000</td>\n            <td>0</td>'.encode('utf-8') in response.data
        # 2
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert token2.token_address.encode('utf-8') in response.data
        assert '<td>2000000</td>\n            <td>2000000</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系4_1＞
    # ＜募集画面＞
    # 新規募集画面の参照
    def test_normal_4_1(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>新規募集'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply']).encode('utf-8') in response.data
        assert self.token_data1['details'].encode('utf-8') in response.data
        assert self.token_data1['returnDetails'].encode('utf-8') in response.data
        assert self.token_data1['expirationDate'].encode('utf-8') in response.data
        assert self.token_data1['memo'].encode('utf-8') in response.data
        assert 'なし'.encode('utf-8') in response.data

    # ＜正常系4_2＞
    # ＜募集画面＞
    # 募集 → 募集管理で確認
    def test_normal_4_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        url_sell = self.url_sell + token.token_address
        # 募集
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302

        # 待機（募集には時間がかかる）
        time.sleep(5)

        # 募集管理
        response = client.get(self.url_positions)

        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        assert '新規募集を受け付けました。募集開始までに数分程かかることがあります。'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert '募集停止'.encode('utf-8') in response.data
        # 募集中の数量が存在する
        assert '<td>1000000</td>\n            <td>0</td>\n            <td>1000000</td>'.encode('utf-8') in response.data

    # ＜正常系4_3＞
    # ＜募集画面＞
    # 募集停止 → 募集管理で確認
    def test_normal_4_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_cancel_order + '0',
        )
        assert response.status_code == 302

        # 待機
        time.sleep(5)

        # 募集管理
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        assert 'テスト会員権'.encode('utf-8') in response.data
        assert 'KAIINKEN'.encode('utf-8') in response.data
        assert '募集開始'.encode('utf-8') in response.data
        # 募集中の数量が0
        assert '<td>1000000</td>\n            <td>1000000</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系5_1＞
    # ＜設定画面＞
    # 再募集→設定画面→各値の更新→設定画面で確認
    def test_normal_5_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]

        ### 再度、募集実施 ###
        url_sell = self.url_sell + token.token_address
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302
        time.sleep(5)

        ### 設定画面 ###
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data3
        )
        assert response.status_code == 302
        time.sleep(10)

        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply']).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['returnDetails'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_small'].encode('utf-8') in response.data
        assert self.token_data3['image_medium'].encode('utf-8') in response.data
        assert self.token_data3['image_large'].encode('utf-8') in response.data

    # ＜正常系5_2＞
    # ＜設定画面＞
    # 同じ値で更新処理　→　各値に変更がないこと
    def test_normal_5_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data3
        )
        assert response.status_code == 302
        time.sleep(2)

        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply']).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['returnDetails'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_small'].encode('utf-8') in response.data
        assert self.token_data3['image_medium'].encode('utf-8') in response.data
        assert self.token_data3['image_large'].encode('utf-8') in response.data
        # 公開中でないことを確認
        assert '公開 <i class="fa fa-arrow-circle-right">'.encode('utf-8') in response.data

    # ＜正常系5_3＞
    # ＜設定画面＞
    # 公開　→　公開中になること、tokenlistに存在すること
    def test_normal_5_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        response = client.post(
            self.url_release,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply']).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['returnDetails'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_small'].encode('utf-8') in response.data
        assert self.token_data3['image_medium'].encode('utf-8') in response.data
        assert self.token_data3['image_large'].encode('utf-8') in response.data
        assert '公開中'.encode('utf-8') in response.data

        # tokenが登録されているか確認
        res_token = get_token_list(shared_contract['TokenList'], token.token_address)
        assert res_token[0] == token.token_address

    # ＜正常系5_4＞
    # ＜設定画面＞
    # 取扱停止　→　一覧・詳細で確認
    def test_normal_5_4(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        response = client.post(
            self.url_invalid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply']).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['returnDetails'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_small'].encode('utf-8') in response.data
        assert self.token_data3['image_medium'].encode('utf-8') in response.data
        assert self.token_data3['image_large'].encode('utf-8') in response.data
        assert '公開中'.encode('utf-8') in response.data
        assert '取扱開始'.encode('utf-8') in response.data
 
        # 一覧
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '取扱停止'.encode('utf-8') in response.data

    # ＜正常系5_5＞
    # ＜設定画面＞
    # 取扱開始　→　詳細で確認
    def test_normal_5_5(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        response = client.post(
            self.url_valid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply']).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['returnDetails'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_small'].encode('utf-8') in response.data
        assert self.token_data3['image_medium'].encode('utf-8') in response.data
        assert self.token_data3['image_large'].encode('utf-8') in response.data
        assert '公開中'.encode('utf-8') in response.data
        assert '取扱停止'.encode('utf-8') in response.data

    # ＜正常系5_6＞
    # ＜設定画面＞
    # 追加発行　→　詳細で確認
    def test_normal_5_6(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        url_add_supply = self.url_add_supply + token.token_address
        response = client.get(url_add_supply)
        assert '<title>追加発行'.encode('utf-8') in response.data

        response = client.post(
            url_add_supply,
            data={
                'addSupply': 10,

            }
        )
        assert response.status_code == 302
        time.sleep(2)

        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply'] + 10).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['returnDetails'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_small'].encode('utf-8') in response.data
        assert self.token_data3['image_medium'].encode('utf-8') in response.data
        assert self.token_data3['image_large'].encode('utf-8') in response.data
        assert '公開中'.encode('utf-8') in response.data
        assert '取扱停止'.encode('utf-8') in response.data

    # ＜正常系6_1＞
    # ＜保有者＞
    # 保有者一覧で確認(1件)
    def test_normal_6_1(self, app, shared_contract):
        # 発行体のpersonalInfo
        register_personalinfo(eth_account['issuer'], shared_contract['PersonalInfo'], self.issuer_encrypted_info)

        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_holders + token.token_address)

        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '<td>10</td>\n            <td>1000000</td>'.encode('utf-8') in response.data

    # ＜正常系6_2＞
    # ＜保有者＞
    # 会員権を譲渡可能に変更　→　約定　→　保有者一覧で確認（複数件）
    def test_normal_6_2(self, app, shared_contract):
        # 投資家のpersonalInfo
        register_personalinfo(eth_account['trader'], shared_contract['PersonalInfo'], self.trader_encrypted_info)

        ### 設定画面 ###
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data1
        )
        assert response.status_code == 302
        time.sleep(10)

        ## 約定 ##
        amount = 20
        orderid = get_latest_orderid_membership(shared_contract['IbetMembershipExchange']) - 1
        take_buy_membership_token(eth_account['trader'], shared_contract['IbetMembershipExchange'], orderid, amount)
        agreementid = get_latest_agreementid_membership(shared_contract['IbetMembershipExchange'], orderid) - 1
        membership_confirm_agreement(eth_account['agent'], shared_contract['IbetMembershipExchange'], orderid, agreementid)

        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data
        # 発行体
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '<td>10</td>\n            <td>999980</td>'.encode('utf-8') in response.data
        # 投資家
        assert eth_account['trader']['account_address'].encode('utf-8') in response.data
        assert 'ﾀﾝﾀｲﾃｽﾄ'.encode('utf-8') in response.data
        assert '<td>20</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系6_3＞
    # ＜保有者＞
    # 保有者詳細
    def test_normal_6_3(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_holder + token.token_address + '/' + eth_account['issuer']['account_address'])
        assert response.status_code == 200
        assert '<title>保有者詳細'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '1234567'.encode('utf-8') in response.data
        assert '東京都'.encode('utf-8') in response.data
        assert '中央区'.encode('utf-8') in response.data
        assert '日本橋11-1'.encode('utf-8') in response.data
        assert '東京マンション１０１'.encode('utf-8') in response.data
        assert '三菱UFJ銀行'.encode('utf-8') in response.data
        assert '東恵比寿支店'.encode('utf-8') in response.data
        assert '普通'.encode('utf-8') in response.data
        assert 'ｶﾌﾞｼｷｶﾞｲｼﾔｹﾂｻｲﾀﾞｲｺｳ'.encode('utf-8') in response.data


    #############################################################################
    # エラー系
    #############################################################################
    # ＜エラー系1_1＞
    # ＜入力値チェック＞
    # 新規発行（必須エラー）
    def test_error_1_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>会員権新規発行'.encode('utf-8') in response.data
        assert '名称は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    # ＜入力値チェック＞
    # 募集（必須エラー）
    def test_error_1_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        # 募集
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_sell + token.token_address,
            data={
            }
        )
        assert response.status_code == 302
        # 新規募集でエラーを確認
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>新規募集'.encode('utf-8') in response.data
        assert '売出価格は必須です。'.encode('utf-8') in response.data