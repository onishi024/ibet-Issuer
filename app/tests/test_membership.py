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

from eth_utils import to_checksum_address

from logging import getLogger
logger = getLogger('api')

class TestMembership(TestBase):

    ##################
    # URL
    ##################
    url_list = 'membership/list' # 発行済一覧
    url_positions = 'membership/positions' # 募集管理
    url_issue = 'membership/issue' # 新規発行
    url_setting = 'membership/setting/' # 詳細設定
    url_sell = 'membership/sell/' # 新規募集
    url_cancel_order = 'membership/cancel_order/' # 募集中止
    url_release = 'membership/release' # 公開
    url_invalid = 'membership/invalid' # 無効化（取扱中止）
    url_valid = 'membership/valid' # 有効化（取扱開始）
    url_add_supply = 'membership/add_supply/' # 追加発行
    url_holders = 'membership/holders/' # 保有者一覧
    url_holder = 'membership/holder/' # 保有者詳細
    url_transfer_ownership = 'membership/transfer_ownership/' # 所有者移転

    ##################
    # テスト用会員権トークン情報
    ##################
    # Token_1：最初に新規発行されるトークン。
    token_data1 = {
        'name': 'テスト会員権',
        'symbol': 'KAIINKEN',
        'totalSupply': 1000000,
        'details': 'details',
        'returnDetails': 'returnDetails',
        'expirationDate': '20191231',
        'memo': 'memo',
        'transferable': 'True',
        'image_small': 'http://hoge.co.jp',
        'image_medium': 'http://hoge.co.jp',
        'image_large': 'http://hoge.co.jp',
    }

    # Token_2：2番目に発行されるトークン。imageなし, transferable:False
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

    # Token_3：設定変更用情報
    token_data3 = {
        'name': 'テスト会員権',
        'symbol': 'KAIINKEN',
        'totalSupply': 1000000,
        'details': '3details',
        'returnDetails': '3returnDetails',
        'expirationDate': '20211231',
        'memo': '3memo',
        'transferable': 'False',
        'image_small': 'http://hoge.co.jp',
        'image_medium': 'http://hoge.co.jp',
        'image_large': 'http://hoge.co.jp'
    }

    @staticmethod
    def get_token(num):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        return tokens[num]

    ##################
    # PersonalInfo情報の暗号化
    ##################
    issuer_personal_info_json = {
        "name":"株式会社１",
        "address":{
            "postal_code":"1234567",
            "prefecture":"東京都",
            "city":"中央区",
            "address1":"日本橋11-1",
            "address2":"東京マンション１０１"
        },
        "bank_account":{
            "bank_name": "三菱UFJ銀行",
            "bank_code": "0005",
            "branch_office": "東恵比寿支店",
            "branch_code": "610",
            "account_type": 1,
            "account_number": "1234567",
            "account_holder": "ｶﾌﾞｼｷｶﾞｲｼﾔｹﾂｻｲﾀﾞｲｺｳ"
        }
    }

    trader_personal_info_json = {
        "name":"ﾀﾝﾀｲﾃｽﾄ",
        "address":{
            "postal_code":"1040053",
            "prefecture":"東京都",
            "city":"中央区",
            "address1":"勝どき6丁目３－２",
            "address2":"ＴＴＴ６０１２"
        },
        "bank_account":{
            "bank_name": "みずほ銀行",
            "bank_code": "0001",
            "branch_office": "日本橋支店",
            "branch_code": "101",
            "account_type": 2,
            "account_number": "7654321",
            "account_holder": "ﾀﾝﾀｲﾃｽﾄｺｳｻﾞ"
        }
    }

    key = RSA.importKey(open('data/rsa/public.pem').read())
    cipher = PKCS1_OAEP.new(key)

    issuer_encrypted_info = \
        base64.encodestring(
            cipher.encrypt(json.dumps(issuer_personal_info_json).encode('utf-8')))

    trader_encrypted_info = \
        base64.encodestring(
            cipher.encrypt(json.dumps(trader_personal_info_json).encode('utf-8')))

    # ＜前処理＞
    def test_normal_0(self, app, shared_contract):
        # Config設定
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = \
            shared_contract['IbetMembershipExchange']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = \
            shared_contract['PersonalInfo']['address']
        self.token_data1['tradableExchange'] = \
            shared_contract['IbetMembershipExchange']['address']
        self.token_data2['tradableExchange'] = \
            shared_contract['IbetMembershipExchange']['address']
        self.token_data3['tradableExchange'] = \
            shared_contract['PersonalInfo']['address']

    # ＜正常系1_1＞
    # ＜会員権の0件確認＞
    #   発行済一覧画面の参照(0件)
    def test_normal_1_1(self, app, shared_contract):
        # 発行済一覧の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>会員権一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜会員権の0件確認＞
    #   募集管理画面の参照(0件)
    def test_normal_1_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2_1＞
    # ＜会員権の1件確認＞
    #   新規発行　→　詳細設定画面の参照
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

        # 詳細設定画面の参照
        token = TestMembership.get_token(0)
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
        assert self.token_data1['tradableExchange'].encode('utf-8') in response.data

    # ＜正常系2_2＞
    # ＜会員権の1件確認＞
    #   発行済一覧画面の参照(1件)
    def test_normal_2_2(self, app, shared_contract):
        token = TestMembership.get_token(0)

        # 発行済一覧画面の参照
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
    #   募集管理画面の参照(1件)
    def test_normal_2_3(self, app, shared_contract):
        token = TestMembership.get_token(0)

        # 募集管理画面の参照
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
    #   新規発行（画像URLなし）　→　詳細設定画面の参照
    def test_normal_3_1(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)

        # 新規発行（Token_2）
        response = client.post(
            self.url_issue,
            data=self.token_data2
        )
        assert response.status_code == 302

        # 2秒待機
        time.sleep(2)

        # DB登録処理
        processorIssueEvent(db)

        # 詳細設定画面の参照
        token = TestMembership.get_token(1)
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
    #   発行済一覧画面の参照（複数件）
    def test_normal_3_2(self, app, shared_contract):
        token1 = TestMembership.get_token(0)
        token2 = TestMembership.get_token(1)

        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>会員権一覧'.encode('utf-8') in response.data

        # Token_1
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token1.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

        # Token_2
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert token2.token_address.encode('utf-8') in response.data

    # ＜正常系3_3＞
    # ＜会員権一覧（複数件）＞
    #   募集管理画面の参照（複数件）
    def test_normal_3_3(self, app, shared_contract):
        token1 = TestMembership.get_token(0)
        token2 = TestMembership.get_token(1)

        # 募集管理画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data

        # Token_1
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token1.token_address.encode('utf-8') in response.data
        assert '<td>1000000</td>\n            <td>1000000</td>\n            <td>0</td>'.\
            encode('utf-8') in response.data

        # Token_2
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert token2.token_address.encode('utf-8') in response.data
        assert '<td>2000000</td>\n            <td>2000000</td>\n            <td>0</td>'.\
            encode('utf-8') in response.data

    # ＜正常系4_1＞
    # ＜募集画面＞
    #   新規募集画面の参照
    #   ※Token_1が対象
    def test_normal_4_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 新規募集画面の参照
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
        assert self.token_data1['tradableExchange'].encode('utf-8') in response.data

    # ＜正常系4_2＞
    # ＜募集画面＞
    #   募集処理 → 募集管理画面の参照
    #   ※Token_1が対象
    def test_normal_4_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        url_sell = self.url_sell + token.token_address

        # 募集処理
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302

        # 募集管理画面の参照
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
    #   募集停止処理 → 募集管理で確認
    #   ※Token_1が対象
    def test_normal_4_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 募集停止処理
        response = client.post(
            self.url_cancel_order + token.token_address,
        )
        assert response.status_code == 302

        # 募集管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>募集管理'.encode('utf-8') in response.data
        assert 'テスト会員権'.encode('utf-8') in response.data
        assert 'KAIINKEN'.encode('utf-8') in response.data
        assert '募集開始'.encode('utf-8') in response.data
        # 募集中の数量が0
        assert '<td>1000000</td>\n            <td>1000000</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系5_1＞
    # ＜詳細設定＞
    #   募集　→　詳細設定（設定変更）　→　詳細設定画面参照
    #   ※Token_1が対象、Token_3の状態に変更
    def test_normal_5_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 募集処理
        url_sell = self.url_sell + token.token_address
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302
        time.sleep(5)

        # 詳細設定：設定変更
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data3
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面の参照
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
        assert self.token_data3['tradableExchange'].encode('utf-8') in response.data

        # データ戻し
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data1
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系5_2＞
    # ＜詳細設定＞
    #   同じ値で更新処理　→　各値に変更がないこと
    def test_normal_5_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        url_setting = self.url_setting + token.token_address

        # 詳細設定：設定変更（Token_1　→　Token_1）
        response = client.post(
            url_setting,
            data=self.token_data1
        )
        assert response.status_code == 302
        time.sleep(2)

        # 詳細設定画面の参照
        response = client.get(url_setting)
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
        assert self.token_data1['tradableExchange'].encode('utf-8') in response.data
        # 公開済でないことを確認
        assert '公開 <i class="fa fa-arrow-circle-right">'.encode('utf-8') in response.data

    # ＜正常系5_3＞
    # ＜設定画面＞
    #   公開処理　→　公開済状態になること
    #   ※Token_1が対象
    def test_normal_5_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 公開処理
        response = client.post(
            self.url_release,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data

    # ＜正常系5_4＞
    # ＜設定画面＞
    #   取扱停止処理　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_4(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 取扱停止処理
        response = client.post(
            self.url_invalid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data
        assert '取扱開始'.encode('utf-8') in response.data

        # 発行済一覧画面の参照
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '取扱停止'.encode('utf-8') in response.data

    # ＜正常系5_5＞
    # ＜設定画面＞
    #   取扱開始　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_5(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 取扱開始処理
        response = client.post(
            self.url_valid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert '取扱停止'.encode('utf-8') in response.data

        # 発行済一覧画面の参照
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系5_6＞
    # ＜設定画面＞
    #   追加発行画面参照　→　追加発行処理　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_6(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        url_add_supply = self.url_add_supply + token.token_address

        # 追加発行画面の参照
        response = client.get(url_add_supply)
        assert '<title>追加発行'.encode('utf-8') in response.data

        # 追加発行処理
        response = client.post(
            url_add_supply,
            data={
                'addSupply': 10,
            }
        )
        assert response.status_code == 302
        time.sleep(5)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>会員権 詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply'] + 10).encode('utf-8') in response.data

    # ＜正常系6_1＞
    # ＜保有者一覧＞
    #   保有者一覧で確認(1件)
    #   ※Token_1が対象
    def test_normal_6_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 発行体のpersonalInfo登録
        register_personalinfo(
            eth_account['issuer'],
            shared_contract['PersonalInfo'],
            self.issuer_encrypted_info
        )

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '<td>10</td>\n            <td>1000000</td>'.encode('utf-8') in response.data

    # ＜正常系6_2＞
    # ＜保有者一覧＞
    #   約定　→　保有者一覧で確認（複数件）
    #   ※Token_1が対象
    def test_normal_6_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 投資家のpersonalInfo登録
        register_personalinfo(
            eth_account['trader'],
            shared_contract['PersonalInfo'],
            self.trader_encrypted_info
        )

        # 約定データの作成
        amount = 20
        exchange = shared_contract['IbetMembershipExchange']
        orderid = get_latest_orderid_membership(exchange) - 1
        take_buy_membership_token(eth_account['trader'], exchange, orderid, amount)
        agreementid = get_latest_agreementid_membership(exchange, orderid) - 1
        membership_confirm_agreement(eth_account['agent'], exchange, orderid, agreementid)

        # 保有者一覧の参照
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
    # ＜保有者一覧＞
    #   保有者詳細
    #   ※Token_1が対象
    def test_normal_6_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 保有者詳細画面の参照
        response = client.get(
            self.url_holder + token.token_address + '/' + \
            eth_account['issuer']['account_address'])
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

    # ＜正常系7_1＞
    # ＜所有者移転＞
    #   所有者移転画面の参照
    #   ※Token_1が対象
    def test_normal_7_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])

        # 所有者移転画面の参照
        response = client.get(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address)
        assert response.status_code == 200
        assert '<title>会員権移転'.encode('utf-8') in response.data
        assert ('value="' + str(issuer_address)).encode('utf-8') in response.data

    # ＜正常系7_2＞
    # ＜所有者移転＞
    #   所有者移転処理　→　保有者一覧の参照
    #   ※Token_1が対象
    def test_normal_7_2(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
                'to_address': trader_address,
                'amount': 10
            }
        )
        assert response.status_code == 302

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 発行体
        assert issuer_address.encode('utf-8') in response.data
        assert '<td>株式会社１'.encode('utf-8') in response.data
        assert '<td>0</td>\n            <td>999980</td>'.encode('utf-8') in response.data

        # 投資家
        assert trader_address.encode('utf-8') in response.data
        assert '<td>ﾀﾝﾀｲﾃｽﾄ'.encode('utf-8') in response.data
        assert '<td>30</td>\n            <td>0</td>'.encode('utf-8') in response.data

    #############################################################################
    # エラー系
    #############################################################################
    # ＜エラー系1_1＞
    # ＜入力値チェック＞
    #   新規発行（必須エラー）
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
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    # ＜入力値チェック＞
    #   募集（必須エラー）
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


    # ＜エラー系2_1＞
    # ＜入力値チェック＞
    #   新規発行（DEXアドレス形式エラー）
    def test_error_2_1(self, app, shared_contract):
        dex_address_error = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
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
                'image_large': '',
                'tradableExchange': dex_address_error
            }
        )
        assert response.status_code == 200
        assert '<title>会員権新規発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data


    # ＜エラー系2_2＞
    # ＜入力値チェック＞
    #   設定画面（DEXアドレス形式エラー）
    def test_error_2_2(self, app, shared_contract):
        dex_address_error = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data={
                'tradableExchange': dex_address_error
            }
        )
        assert response.status_code == 200
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系3_1＞
    # ＜所有者移転＞
    #   URLパラメータチェック：token_addressが無効
    def test_error_3_1(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + error_address + '/' + issuer_address ,
            data={
                'to_address': trader_address,
                'amount': 10
            }
        )
        assert response.status_code == 404

    # ＜エラー系3_2＞
    # ＜所有者移転＞
    #    URLパラメータチェック：account_addressが無効
    def test_error_3_2(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + error_address ,
            data={
                'to_address': trader_address,
                'amount': 10
            }
        )
        assert response.status_code == 404

    # ＜エラー系3_3＞
    # ＜所有者移転＞
    #   入力値チェック：必須チェック
    def test_error_3_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
            }
        )
        assert response.status_code == 200
        assert '移転先は必須です。'.encode('utf-8') in response.data
        assert '移転数量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3_4＞
    # ＜所有者移転＞
    #   入力値チェック：to_addressが無効
    def test_error_3_4(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
                'to_address': error_address,
                'amount': 10
            }
        )
        assert response.status_code == 200
        assert '移転先は無効なアドレスです。'.encode('utf-8') in response.data

    # ＜エラー系3_5＞
    # ＜所有者移転＞
    #   入力値チェック：amountが上限超過
    def test_error_3_5(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
                'to_address': trader_address,
                'amount': 100000001
            }
        )
        assert response.status_code == 200
        assert '移転数量は100,000,000が上限です。'.encode('utf-8') in response.data

    # ＜エラー系3_6＞
    # ＜所有者移転＞
    #   入力値チェック：amountが残高超
    def test_error_3_6(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
                'to_address': trader_address,
                'amount': 1000
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data
