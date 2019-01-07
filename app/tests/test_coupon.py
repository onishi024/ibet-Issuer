# -*- coding:utf-8 -*-
import pytest
import os
import time

from .conftest import TestBase
from .account_config import eth_account
from config import Config
from .contract_modules import *
from ..models import Token

from logging import getLogger
logger = getLogger('api')

class TestCoupon(TestBase):

    ##################
    # URL
    ##################
    url_list = 'coupon/list' # 発行済一覧
    url_issue = 'coupon/issue' # 新規発行
    url_setting = 'coupon/setting/' # 詳細設定
    url_valid = 'coupon/valid' # 有効化（取扱開始）
    url_invalid = 'coupon/invalid' # 無効化（取扱中止）
    url_add_supply = 'coupon/add_supply/' # 追加発行
    url_transfer = 'coupon/transfer' # 割当
    url_transfer_ownership = 'coupon/transfer_ownership/' # 所有者移転
    url_holders = 'coupon/holders/' # 保有者一覧
    url_holder = 'coupon/holder/' # 保有者詳細
    url_positions = 'coupon/positions' # 売出管理
    url_sell = 'coupon/sell/' # 新規売出
    url_cancel_order = 'coupon/cancel_order/' # 売出中止
    url_release = 'coupon/release' # 公開

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
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = \
            shared_contract['IbetStraightBondExchange']['address']
        Config.WHITE_LIST_CONTRACT_ADDRESS = \
            shared_contract['WhiteList']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = \
            shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = \
            shared_contract['PersonalInfo']['address']
        Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = \
            shared_contract['IbetCouponExchange']['address']

        # personalinfo登録
        register_personalinfo(
            eth_account['issuer'],
            shared_contract['PersonalInfo'],
            self.issuer_encrypted_info
        )

        register_personalinfo(
            eth_account['trader'],
            shared_contract['PersonalInfo'],
            self.trader_encrypted_info
        )

    # ＜正常系1_1＞
    #   発行済一覧画面の参照(0件)
    def test_normal_1_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        # 発行済一覧の参照
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜0件確認＞
    #   売出管理画面の参照(0件)
    def test_normal_1_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        # 売出管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2＞
    # ＜新規発行＞
    #   新規発行　→　詳細設定画面の参照
    def test_normal_2(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)

        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テストクーポン',
                'symbol': 'COUPON',
                'totalSupply': 2000000,
                'expirationDate': '20191231',
                'transferable': True,
                'details': 'details詳細',
                'memo': 'memoメモ',
                'image_small': 'https://test.com/image_small.jpg',
                'image_medium': 'https://test.com/image_medium.jpg',
                'image_large': 'https://test.com/image_large.jpg',
                'tradableExchange': shared_contract['IbetCouponExchange']['address']
            }
        )
        assert response.status_code == 302

        # 5秒待機
        time.sleep(10)

        # DB登録処理
        processorIssueEvent(db)

        # 詳細設定画面の参照
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        response = client.get(self.url_setting + tokens[0].token_address)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data
        assert 'details詳細'.encode('utf-8') in response.data
        assert 'memoメモ'.encode('utf-8') in response.data
        assert 'https://test.com/image_small.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_medium.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_large.jpg'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

    # ＜正常系3_1＞
    # ＜1件確認＞
    #   発行済一覧画面の参照(1件)
    def test_normal_3_1(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '有効'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data

    # ＜正常系3_2＞
    # ＜1件確認＞
    #   売出管理画面の参照(1件)
    def test_normal_3_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '<td>2000000</td>\n            <td>2000000</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系4＞
    # ＜設定変更＞
    #   クーポン設定変更　→　詳細設定画面で確認
    def test_normal_4(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_setting = self.url_setting + tokens[0].token_address
        client = self.client_with_admin_login(app)

        # 設定変更
        response = client.post(
            url_setting,
            data={
                'details': 'details詳細2',
                'memo': 'memoメモ2',
                'tradableExchange': shared_contract['IbetCouponExchange']['address'],
                'image_small': 'https://test.com/image_small2.jpg',
                'image_medium': 'https://test.com/image_medium2.jpg',
                'image_large': 'https://test.com/image_large2.jpg',
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data
        assert 'details詳細2'.encode('utf-8') in response.data
        assert 'memoメモ2'.encode('utf-8') in response.data
        assert 'https://test.com/image_small2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_medium2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_large2.jpg'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

        # データ戻し
        response = client.post(
            url_setting,
            data={
                'details': 'details詳細',
                'memo': 'memoメモ',
                'tradableExchange': shared_contract['IbetCouponExchange']['address'],
                'image_small': 'https://test.com/image_small.jpg',
                'image_medium': 'https://test.com/image_medium.jpg',
                'image_large': 'https://test.com/image_large.jpg',
            }
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系5_1＞
    # ＜有効化・無効化＞
    #   無効化　→　発行済一覧で確認
    def test_normal_5_1(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)

        # 無効化
        response = client.post(
            self.url_invalid,
            data={
                'token_address': tokens[0].token_address
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        # 一覧で確認
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '無効'.encode('utf-8') in response.data

    # ＜正常系5_2＞
    # ＜有効化・無効化＞
    #   有効化　→　発行済一覧で確認
    def test_normal_5_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)

        # 有効化
        response = client.post(
            self.url_valid,
            data={
                'token_address': tokens[0].token_address
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(2)

        # 一覧で確認
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '有効'.encode('utf-8') in response.data

    # ＜正常系6＞
    # ＜追加発行＞
    #   追加発行 →　詳細背定画面で確認
    def test_normal_6(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_add_supply = self.url_add_supply + tokens[0].token_address
        url_setting = self.url_setting + tokens[0].token_address
        client = self.client_with_admin_login(app)

        # 追加発行画面（GET）
        response = client.get(url_add_supply)
        assert response.status_code == 200
        assert '<title>クーポン追加発行'.encode('utf-8') in response.data
        assert tokens[0].token_address.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data

        # 追加発行
        response = client.post(
            url_add_supply,
            data={
                'addSupply': 100
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        # 詳細設定画面で確認
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert '2000100'.encode('utf-8') in response.data

    # ＜正常系7＞
    # ＜割当＞
    #   クーポン割当　→　保有者一覧で確認
    def test_normal_7(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)

        # 割当処理
        response = client.post(
            self.url_transfer,
            data={
                'token_address': tokens[0].token_address,
                'to_address': eth_account['trader']['account_address'],
                'amount': 100,
            }
        )
        assert response.status_code == 200
        time.sleep(5)

        # 保有者一覧画面の参照
        response = client.get(self.url_holders + tokens[0].token_address)
        assert response.status_code == 200
        assert '<title>クーポン保有者一覧'.encode('utf-8') in response.data
        # issuer
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data # issuerの保有数量
        # trader
        assert eth_account['trader']['account_address'].encode('utf-8') in response.data
        assert 'ﾀﾝﾀｲﾃｽﾄ'.encode('utf-8') in response.data
        assert '100'.encode('utf-8') in response.data # traderの保有数量

    # ＜正常系8＞
    # ＜保有者詳細＞
    #   保有者詳細
    def test_normal_8(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)

        # 保有者詳細画面の参照
        response = client.get(self.url_holder + tokens[0].token_address + '/' + \
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

    # ＜正常系9_1＞
    # ＜売出＞
    #   新規売出画面の参照
    def test_normal_9_1(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 売出画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>新規売出'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000100'.encode('utf-8') in response.data
        assert 'details詳細'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert 'memoメモ'.encode('utf-8') in response.data
        assert 'なし'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

    # ＜正常系9_2＞
    # ＜売出＞
    #   売出 → 売出管理画面で確認
    def test_normal_9_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        url_sell = self.url_sell + token.token_address

        # 売出処理
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302

        # 売出管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert '新規売出を受け付けました。売出開始までに数分程かかることがあります。'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '売出停止'.encode('utf-8') in response.data
        # 売出中の数量が存在する
        assert '<td>2000100</td>\n            <td>0</td>\n            <td>2000000</td>'.encode('utf-8') in response.data

    # ＜正常系9_3＞
    # ＜売出＞
    #   売出停止 → 売出管理画面で確認
    def test_normal_9_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 売出停止処理
        response = client.post(
            self.url_cancel_order + token.token_address,
        )
        assert response.status_code == 302

        # 売出管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '売出開始'.encode('utf-8') in response.data
        # 売出中の数量が0
        assert '<td>2000100</td>\n            <td>2000000</td>\n            <td>0</td>'.encode('utf-8') in response.data

    # ＜正常系10_1＞
    # ＜所有者移転＞
    #   所有者移転画面の参照
    def test_normal_10_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])

        # 所有者移転画面の参照
        response = client.get(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address)
        assert response.status_code == 200
        assert '<title>所有者移転'.encode('utf-8') in response.data
        assert ('value="' + str(issuer_address)).encode('utf-8') in response.data

    # ＜正常系10_2＞
    # ＜所有者移転＞
    #   所有者移転処理　→　保有者一覧の参照
    def test_normal_10_2(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
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
        assert '<title>クーポン保有者一覧'.encode('utf-8') in response.data

        # 発行体
        assert issuer_address.encode('utf-8') in response.data
        assert '<td>株式会社１</td>\n            <td>1999990</td>\n            <td>0</td>'.\
            encode('utf-8') in response.data

        # 投資家
        assert trader_address.encode('utf-8') in response.data
        assert '<td>ﾀﾝﾀｲﾃｽﾄ</td>\n            <td>110</td>\n            <td>0</td>'.\
            encode('utf-8') in response.data

    # ＜正常系11＞
    # ＜公開＞
    #   公開処理　→　公開済状態になること
    def test_normal_11(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

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
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data

    #############################################################################
    # エラー系
    #############################################################################
    # ＜エラー系1＞
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
        assert '<title>クーポン発行'.encode('utf-8') in response.data
        assert 'クーポン名は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系2＞
    #   追加発行（必須エラー）
    def test_error_1_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_add_supply = self.url_add_supply + tokens[0].token_address
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            url_add_supply,
            data={}
        )
        assert response.status_code == 200
        assert '<title>クーポン追加発行'.encode('utf-8') in response.data
        assert '追加発行する数量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3＞
    #   割当（必須エラー）
    def test_error_1_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={}
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert 'クーポンアドレスは必須です。'.encode('utf-8') in response.data
        assert '割当先アドレスは必須です。'.encode('utf-8') in response.data
        assert '割当数量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    # ＜入力値チェック＞
    #   売出（必須エラー）
    def test_error_1_4(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        # 売出
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_sell + token.token_address,
            data={
            }
        )
        assert response.status_code == 302
        # 新規売出でエラーを確認
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>新規売出'.encode('utf-8') in response.data
        assert '売出価格は必須です。'.encode('utf-8') in response.data

    # ＜エラー系2_1＞
    # ＜入力値チェック＞
    #   新規発行（DEXアドレス形式エラー）
    def test_error_2_1(self, app, shared_contract):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テストクーポン',
                'symbol': 'COUPON',
                'totalSupply': 2000000,
                'expirationDate': '20191231',
                'transferable': True,
                'details': 'details詳細',
                'memo': 'memoメモ',
                'image_small': 'https://test.com/image_small.jpg',
                'image_medium': 'https://test.com/image_medium.jpg',
                'image_large': 'https://test.com/image_large.jpg',
                'tradableExchange': error_address
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_2＞
    # ＜入力値チェック＞
    #   設定画面（DEXアドレス形式エラー）
    def test_error_2_2(self, app, shared_contract):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_setting = self.url_setting + tokens[0].token_address
        client = self.client_with_admin_login(app)
        response = client.post(
            url_setting,
            data={
                'details': 'details詳細2',
                'memo': 'memoメモ2',
                'tradableExchange': error_address,
                'image_small': 'https://test.com/image_small2.jpg',
                'image_medium': 'https://test.com/image_medium2.jpg',
                'image_large': 'https://test.com/image_large2.jpg',
            }
        )
        assert response.status_code == 302
        time.sleep(2)

        response = client.get(url_setting)
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
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
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
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
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
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
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
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
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
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
                'to_address': trader_address,
                'amount': 2000001
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data
