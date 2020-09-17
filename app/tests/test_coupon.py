# -*- coding:utf-8 -*-
import time
from datetime import datetime

import pytest
import json
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from eth_utils import to_checksum_address

from config import Config
from .conftest import TestBase
from .utils import contract_utils_common
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, index_transfer_event, clean_issue_event
from .utils.contract_utils_coupon import apply_for_offering
from .utils.contract_utils_personal_info import register_personal_info
from ..models import Token, Transfer


class TestCoupon(TestBase):

    #############################################################################
    # テスト対象URL
    #############################################################################
    url_list = 'coupon/list'  # 発行済一覧
    url_issue = 'coupon/issue'  # 新規発行
    url_setting = 'coupon/setting/'  # 詳細設定
    url_valid = 'coupon/valid'  # 有効化（取扱開始）
    url_invalid = 'coupon/invalid'  # 無効化（取扱中止）
    url_add_supply = 'coupon/add_supply/'  # 追加発行
    url_start_initial_offering = 'coupon/start_initial_offering'  # 募集申込開始
    url_stop_initial_offering = 'coupon/stop_initial_offering'  # 募集申込停止
    url_applications = 'coupon/applications/'  # 募集申込一覧
    url_get_applications = 'coupon/get_applications/'  # 募集申込一覧
    url_applications_csv_download = 'coupon/applications_csv_download'  # 申込者リストCSVダウンロード
    url_allocate = 'coupon/allocate'  # 割当（募集申込）
    url_transfer = 'coupon/transfer'  # 割当
    url_bulk_transfer = 'coupon/bulk_transfer'  # 一括割当
    url_transfer_ownership = 'coupon/transfer_ownership/'  # 所有者移転
    url_holders = 'coupon/holders/'  # 保有者一覧
    url_get_holders = 'coupon/get_holders/'  # 保有者一覧（API）
    url_holders_csv_download = 'coupon/holders_csv_download'  # 保有者一覧CSVダウンロード
    url_get_token_name = 'coupon/get_token_name/'  # トークン名取得（API）
    url_holder = 'coupon/holder/'  # 保有者詳細
    url_positions = 'coupon/positions'  # 売出管理
    url_sell = 'coupon/sell/'  # 新規売出
    url_cancel_order = 'coupon/cancel_order/'  # 売出中止
    url_release = 'coupon/release'  # 公開
    url_usage_history = 'coupon/usage_history/'  # 利用履歴
    url_get_usage_history_coupon = 'coupon/get_usage_history_coupon/'  # 利用履歴
    url_used_csv_download = 'coupon/used_csv_download'  # 利用履歴CSVダウンロード
    url_token_tracker = 'coupon/token/track/'  # トークン追跡

    #############################################################################
    # PersonalInfo情報の暗号化
    #############################################################################
    issuer_personal_info_json = {
        "name": "株式会社１",
        "address": {
            "postal_code": "1234567",
            "prefecture": "東京都",
            "city": "中央区",
            "address1": "日本橋11-1",
            "address2": "東京マンション１０１"
        },
        "email": "abcd1234@aaa.bbb.cc",
        "birth": "20190902"
    }

    trader_personal_info_json = {
        "name": "ﾀﾝﾀｲﾃｽﾄ",
        "address": {
            "postal_code": "1040053",
            "prefecture": "東京都",
            "city": "中央区",
            "address1": "勝どき1丁目１－２ー３",
            "address2": ""
        },
        "email": "abcd1234@aaa.bbb.cc",
        "birth": "20191102"
    }

    key = RSA.importKey(open('data/rsa/public.pem').read())
    cipher = PKCS1_OAEP.new(key)

    issuer_encrypted_info = \
        base64.encodebytes(
            cipher.encrypt(json.dumps(issuer_personal_info_json).encode('utf-8')))

    trader_encrypted_info = \
        base64.encodebytes(
            cipher.encrypt(json.dumps(trader_personal_info_json).encode('utf-8')))

    #############################################################################
    # テスト（正常系）
    #############################################################################

    # ＜前処理＞
    def test_normal_0(self, shared_contract, db):
        # personalinfo登録
        register_personal_info(
            eth_account['issuer'],
            shared_contract['PersonalInfo'],
            self.issuer_encrypted_info
        )

        register_personal_info(
            eth_account['trader'],
            shared_contract['PersonalInfo'],
            self.trader_encrypted_info
        )

    # ＜正常系1_1＞
    #   発行済一覧画面の参照(0件)
    def test_normal_1_1(self, app):
        client = self.client_with_admin_login(app)
        # 発行済一覧の参照
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜0件確認＞
    #   売出管理画面の参照(0件)
    def test_normal_1_2(self, app):
        client = self.client_with_admin_login(app)
        # 売出管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2_1＞
    # ＜新規発行＞
    #   新規発行
    def test_normal_2_1(self, app, shared_contract):
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
                'return_details': 'return詳細',
                'memo': 'memoメモ',
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': shared_contract['IbetCouponExchange']['address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系2_2＞
    # ＜新規発行＞
    #   DB取込前確認
    def test_normal_2_2(self, app):
        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data

    # ＜正常系2_3＞
    # ＜新規発行＞
    #   新規発行（DB取込）　→　詳細設定画面の参照
    def test_normal_2_3(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)

        # DB登録処理
        processor_issue_event(db)

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
        assert 'return詳細'.encode('utf-8') in response.data
        assert 'memoメモ'.encode('utf-8') in response.data
        assert 'https://test.com/image_1.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_3.jpg'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

    # ＜正常系2_4＞
    # ＜新規発行＞
    #   新規発行：譲渡制限あり
    def test_normal_2_4(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)

        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テストクーポン',
                'symbol': 'COUPON',
                'totalSupply': 2000000,
                'expirationDate': '20191231',
                'transferable': False,
                'details': 'details詳細',
                'return_details': 'return詳細',
                'memo': 'memoメモ',
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': shared_contract['IbetCouponExchange']['address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        response = client.get(self.url_setting + tokens[1].token_address)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert 'details詳細'.encode('utf-8') in response.data
        assert 'return詳細'.encode('utf-8') in response.data
        assert 'memoメモ'.encode('utf-8') in response.data
        assert 'https://test.com/image_1.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_3.jpg'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

    # ＜正常系2_5＞
    # ＜発行画面表示＞
    def test_normal_2_5(self, app):
        client = self.client_with_admin_login(app)

        # 新規発行画面の表示
        response = client.get(self.url_issue, )
        assert response.status_code == 200

        assert '<title>クーポン発行'.encode('utf-8') in response.data
        assert 'クーポン名'.encode('utf-8') in response.data

    # ＜正常系3_1＞
    # ＜1件確認＞
    #   発行済一覧画面の参照(1件)
    def test_normal_3_1(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data

    # ＜正常系3_2＞
    # ＜1件確認＞
    #   売出管理画面の参照(1件)
    def test_normal_3_2(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '<td>2,000,000</td>\n                <td>2,000,000</td>\n                <td>0</td>'.\
                   encode('utf-8') in response.data

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
                'return_details': 'return詳細2',
                'memo': 'memoメモ2',
                'expirationDate': '20200101',
                'transferable': 'False',
                'tradableExchange': shared_contract['IbetCouponExchange']['address'],
                'image_1': 'https://test.com/image_12.jpg',
                'image_2': 'https://test.com/image_22.jpg',
                'image_3': 'https://test.com/image_32.jpg',
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
        assert '20200101'.encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert 'details詳細2'.encode('utf-8') in response.data
        assert 'return詳細2'.encode('utf-8') in response.data
        assert 'memoメモ2'.encode('utf-8') in response.data
        assert 'https://test.com/image_12.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_22.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_32.jpg'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

        # データ戻し
        response = client.post(
            url_setting,
            data={
                'details': 'details詳細',
                'return_details': 'return詳細',
                'memo': 'memoメモ',
                'expirationDate': '20191231',
                'transferable': 'True',
                'tradableExchange': shared_contract['IbetCouponExchange']['address'],
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
            }
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系5_1＞
    # ＜有効化・無効化＞
    #   無効化　→　発行済一覧で確認
    def test_normal_5_1(self, app):
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

        # 一覧で確認
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '停止中'.encode('utf-8') in response.data

    # ＜正常系5_2＞
    # ＜有効化・無効化＞
    #   有効化　→　発行済一覧で確認
    def test_normal_5_2(self, app):
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

        # 一覧で確認
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系6＞
    # ＜追加発行＞
    #   追加発行 →　詳細背定画面で確認
    def test_normal_6(self, app):
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
        time.sleep(10)

        # 詳細設定画面で確認
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert '2000100'.encode('utf-8') in response.data

    # ＜正常系7_1＞
    # ＜割当＞
    #   クーポン割当　→　保有者一覧で確認
    def test_normal_7_1(self, app):
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
        time.sleep(10)

        # 保有者一覧画面の参照
        response = client.get(self.url_holders + tokens[0].token_address)
        assert response.status_code == 200
        assert '<title>クーポン保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + tokens[0].token_address)
        response_data_list = json.loads(response.data)

        assert response.status_code == 200
        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '発行体１' == response_data['name']
                assert '--' == response_data['postal_code']
                assert '--' == response_data['address']
                assert '--' == response_data['email']
                assert '--' == response_data['birth_date']
                assert 2000000 == response_data['balance']
                assert 0 == response_data['used']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１－２−３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 100 == response_data['balance']
                assert 0 == response_data['used']
            else:
                pytest.raises(AssertionError)

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + tokens[0].token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert 'テストクーポン' == response_data

    # ＜正常系7_2＞
    # ＜割当＞
    #   クーポン割当画面表示
    def test_normal_7_2(self, app):
        client = self.client_with_admin_login(app)

        # 割当処理
        response = client.get(self.url_transfer)
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data

    # ＜正常系7_3＞
    # ＜一括割当画面表示＞
    #   クーポン一括割当
    def test_normal_7_3(self, app):
        client = self.client_with_admin_login(app)

        # 一括割当処理(GET)
        response = client.get(self.url_bulk_transfer)
        assert response.status_code == 200
        assert '<title>クーポン一括割当'.encode('utf-8') in response.data

        # CSV一括割当処理(POST)
        response = client.post(self.url_bulk_transfer)
        assert response.status_code == 200

    # ＜正常系8＞
    # ＜保有者詳細＞
    #   保有者詳細
    def test_normal_8(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)

        # 保有者詳細画面の参照
        response = client.get(
            self.url_holder + tokens[0].token_address + '/' + eth_account['issuer']['account_address']
        )
        assert response.status_code == 200
        assert '<title>保有者詳細'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '1234567'.encode('utf-8') in response.data
        assert '東京都'.encode('utf-8') in response.data
        assert '中央区'.encode('utf-8') in response.data
        assert '日本橋11-1'.encode('utf-8') in response.data
        assert '東京マンション１０１'.encode('utf-8') in response.data

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
        assert "{:,}".format(2000100).encode('utf-8') in response.data
        assert 'details詳細'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert 'なし'.encode('utf-8') in response.data
        assert shared_contract['IbetCouponExchange']['address'].encode('utf-8') in response.data

    # ＜正常系9_2＞
    # ＜売出＞
    #   売出 → 売出管理画面で確認
    def test_normal_9_2(self, app):
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
        # 売出中の数量が存在する
        assert '<td>2,000,100</td>\n                <td>0</td>\n                <td>2,000,000</td>'.\
                   encode('utf-8') in response.data

    # ＜正常系9_3＞
    # ＜売出＞
    #   売出停止 → 売出管理画面で確認
    def test_normal_9_3(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 売出停止処理
        response = client.post(
            self.url_cancel_order + token.token_address + "/1",
        )
        assert response.status_code == 302

        # 売出管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        # 売出中の数量が0
        assert '<td>2,000,100</td>\n                <td>2,000,000</td>\n                <td>0</td>'.\
                   encode('utf-8') in response.data

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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
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

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)

        assert response.status_code == 200

        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '発行体１' == response_data['name']
                assert '--' == response_data['postal_code']
                assert '--' == response_data['address']
                assert '--' == response_data['email']
                assert '--' == response_data['birth_date']
                assert 1999990 == response_data['balance']
                assert 0 == response_data['used']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１－２ー３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 110 == response_data['balance']
                assert 0 == response_data['used']
            else:
                pytest.raises(AssertionError)

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert 'テストクーポン' == response_data

    # ＜正常系11＞
    # ＜公開＞
    #   公開処理　→　公開済状態になること
    def test_normal_11(self, app):
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

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data

    # ＜正常系12_1＞
    # ＜募集申込開始・停止＞
    #   初期状態：募集申込停止中（詳細設定画面で確認）
    #   ※Token_1が対象
    def test_normal_12_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

    # ＜正常系12_2＞
    # ＜募集申込開始・停止＞
    #   募集申込開始　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_12_2(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 募集申込開始
        response = client.post(
            self.url_start_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert '募集申込停止'.encode('utf-8') in response.data

    # ＜正常系12_3＞
    # ＜募集申込開始・停止＞
    #   ※12_2の続き
    #   募集申込停止　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_12_3(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 募集申込停止
        response = client.post(
            self.url_stop_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

        # 募集申込状態に戻す
        response = client.post(
            self.url_start_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

    # ＜正常系13_1＞
    # ＜募集申込一覧参照＞
    #   0件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_13_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        # 募集申込一覧参照
        response = client.get(self.url_applications + str(token.token_address))
        assert response.status_code == 200
        assert '<title>募集申込一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系13_2＞
    # ＜募集申込一覧参照＞
    #   1件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_13_2(self, db, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        token_address = str(token.token_address)
        trader_address = eth_account['trader']['account_address']

        # 募集申込データの作成：投資家
        apply_for_offering(
            db,
            eth_account['trader'],
            token_address
        )

        # 募集申込一覧参照
        response = client.get(self.url_applications + token_address)
        assert response.status_code == 200
        assert '<title>募集申込一覧'.encode('utf-8') in response.data

        applications = client.get(self.url_get_applications + token_address)
        assert trader_address.encode('utf-8') in applications.data

    # ＜正常系14_1＞
    # ＜割当（募集申込）＞
    #   ※12_2の続き
    #   割当（募集申込）画面参照：GET
    #   ※Token_1が対象
    def test_normal_14_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        token_address = str(token.token_address)
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_allocate + '/' + token_address + '/' + trader_address
        response = client.get(url)
        assert response.status_code == 200
        assert 'クーポン割当'.encode('utf-8') in response.data
        assert token_address.encode('utf-8') in response.data
        assert trader_address.encode('utf-8') in response.data

    # ＜正常系14_2＞
    # ＜割当（募集申込）＞
    #   ※10_2, 12_2の後に実施
    #   割当（募集申込）処理　→　保有者一覧参照
    #   ※Token_1が対象
    def test_normal_14_2(self, db, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        token_address = str(token.token_address)
        issuer_address = eth_account['issuer']['account_address']
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_allocate + '/' + token_address + '/' + trader_address
        response = client.post(url, data={'amount': 10})
        assert response.status_code == 302

        # Transferイベント登録
        index_transfer_event(
            db,
            '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
            token.token_address,
            issuer_address,
            trader_address,
            10,
            block_timestamp=datetime.utcnow()
        )

        # 保有者一覧の参照
        response = client.get(self.url_holders + token_address)
        assert response.status_code == 200
        assert '<title>クーポン保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200

        # issuer
        assert issuer_address == response_data[0]['account_address']
        assert '発行体１' == response_data[0]['name']
        assert '--' == response_data[0]['postal_code']
        assert '--' == response_data[0]['address']
        assert '--' == response_data[0]['email']
        assert '--' == response_data[0]['birth_date']
        assert 1999980 == response_data[0]['balance']
        assert 0 == response_data[0]['used']

        # trader
        assert trader_address == response_data[1]['account_address']
        assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data[1]['name']
        assert '1040053' == response_data[1]['postal_code']
        assert '東京都中央区　勝どき1丁目１－２ー３' == response_data[1]['address']
        assert 'abcd1234@aaa.bbb.cc' == response_data[1]['email']
        assert '20191102' == response_data[1]['birth_date']
        assert 120 == response_data[1]['balance']
        assert 0 == response_data[1]['used']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert 'テストクーポン' == response_data

    # ＜正常系15＞
    # ＜保有者一覧CSVダウンロード＞
    #   保有者一覧CSVが取得できること
    def test_normal_15(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        token_address = str(token.token_address)

        # csvダウンロード
        url = self.url_holders_csv_download
        response = client.post(url, data={'token_address': token_address})
        assert response.status_code == 200

    # ＜正常系16＞
    #   トークン追跡
    def test_normal_16(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 登録済みのトランザクションハッシュを取得
        transfer_event = Transfer.query.filter_by(token_address=token.token_address).first()
        tx_hash = transfer_event.transaction_hash

        # トークン追跡の参照
        response = client.get(self.url_token_tracker + token.token_address)

        assert response.status_code == 200
        assert '<title>トークン追跡'.encode('utf-8') in response.data
        assert tx_hash.encode('utf-8') in response.data

    # ＜正常系17_1＞
    # ＜クーポン利用履歴画面＞
    #   クーポン利用履歴画面が表示できること
    def test_normal_17_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        token_address = str(token.token_address)

        url = self.url_usage_history + token_address
        response = client.get(url)
        assert response.status_code == 200

    # ＜正常系17_2＞
    # ＜クーポン利用履歴（API）＞
    #   クーポン利用履歴が取得できること（0件）
    def test_normal_17_2(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]

        token_address = str(token.token_address)

        url = self.url_get_usage_history_coupon + token_address
        response = client.get(url)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert len(response_data) == 0

    # ＜正常系17_3＞
    # ＜クーポン利用履歴（API）＞
    #   クーポン利用履歴が取得できること（1件）
    def test_normal_17_3(self, app, db):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        trader_account = eth_account['trader']['account_address']
        balance = 7
        total_used_amont = 2
        used_amount = 1

        event = contract_utils_common.index_consume_event(
            db,
            '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
            token.token_address,
            trader_account,
            balance,
            total_used_amont,
            used_amount,
            datetime(2020, 5, 31, 0, 59, 59, 123)
        )

        token_address = str(token.token_address)

        url = self.url_get_usage_history_coupon + token_address
        response = client.get(url)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert len(response_data) == 1
        assert response_data[0]['block_timestamp'] == '2020/05/31 09:59:59 +0900'
        assert response_data[0]['consumer'] == trader_account
        assert response_data[0]['value'] == used_amount

        # 後処理
        db.session.delete(event)

    # ＜正常系17_4＞
    # ＜利用履歴CSVダウンロード＞
    #   クーポン利用履歴CSVが取得できること
    def test_normal_17_4(self, app, db):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[0]
        trader_account = eth_account['trader']['account_address']
        balance = 7
        total_used_amount = 2
        used_amount = 1

        event = contract_utils_common.index_consume_event(
            db,
            '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
            token.token_address,
            trader_account,
            balance,
            total_used_amount,
            used_amount,
            datetime(2020, 5, 31, 0, 59, 59, 123)
        )

        token_address = str(token.token_address)

        response = client.post(
            self.url_used_csv_download,
            data={
                'token_address': token_address
            }
        )
        assumed_csv = \
            'token_name,token_address,timestamp,account_address,amount\n' + \
            f'テストクーポン,{token.token_address},2020/05/31 09:59:59 +0900,{trader_account},{used_amount}\n'

        assert response.status_code == 200
        assert assumed_csv == response.data.decode('sjis')

        # 後処理
        db.session.delete(event)

    #############################################################################
    # テスト（エラー系）
    #############################################################################

    # ＜エラー系1＞
    #   新規発行（必須エラー）
    def test_error_1_1(self, app):
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
    def test_error_1_2(self, app):
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
        assert '追加発行量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3＞
    #   割当（必須エラー）
    def test_error_1_3(self, app):
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

    # ＜エラー系1_4＞
    # ＜入力値チェック＞
    #   売出（必須エラー）
    def test_error_1_4(self, app):
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
    def test_error_2_1(self, app):
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
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': error_address
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_2＞
    # ＜入力値チェック＞
    #   設定画面（DEXアドレス形式エラー）
    def test_error_2_2(self, app):
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
                'image_1': 'https://test.com/image_12.jpg',
                'image_2': 'https://test.com/image_22.jpg',
                'image_3': 'https://test.com/image_32.jpg',
            }
        )
        assert response.status_code == 200
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_3＞
    #   追加発行（上限エラー）
    def test_error_2_3(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_add_supply = self.url_add_supply + tokens[0].token_address
        url_setting = self.url_setting + tokens[0].token_address
        client = self.client_with_admin_login(app)

        # 追加発行画面（GET）
        response = client.get(url_add_supply)
        assert response.status_code == 200
        assert '<title>クーポン追加発行'.encode('utf-8') in response.data
        assert tokens[0].token_address.encode('utf-8') in response.data
        assert '2000100'.encode('utf-8') in response.data

        # 追加発行
        response = client.post(
            url_add_supply,
            data={
                'addSupply': 100000000,
                'totalSupply': 2000100,
            }
        )
        assert response.status_code == 302
        response = client.get(url_add_supply)
        assert '総発行量と追加発行量の合計は、100,000,000が上限です。'.encode('utf-8') in response.data
        time.sleep(10)

        # 詳細設定画面で確認
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン詳細設定'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert '2000100'.encode('utf-8') in response.data

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
            self.url_transfer_ownership + error_address + '/' + issuer_address,
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
            self.url_transfer_ownership + token.token_address + '/' + error_address,
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

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
            data={
                'to_address': trader_address,
                'amount': 2000001
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data

    # ＜エラー系4_1＞
    # ＜追加発行＞
    #   追加発行 →　何らかの影響で指定したトークンが存在しない
    def test_error_4_1(self, app):
        url_add_supply = self.url_add_supply + "0x1111"  # 不正なアドレス
        client = self.client_with_admin_login(app)

        # 追加発行画面（GET）
        response = client.get(url_add_supply)
        assert response.status_code == 404  # abortされる

    # ＜エラー系4_2＞
    # ＜追加発行＞
    #   詳細設定 →　何らかの影響で指定したトークンが存在しない
    def test_error_4_2(self, app):
        url_setting = self.url_setting + "0x2222"  # 不正なアドレス
        client = self.client_with_admin_login(app)

        # 詳細設定画面（GET）
        response = client.get(url_setting)
        assert response.status_code == 404  # abortされる

    # ＜エラー系4_3＞
    # ＜売出＞
    #   新規売出　→　何らかの影響で指定したトークンが存在しない
    def test_error4_3(self, app):
        # 売出画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_sell + "0x3333")  # 不正なアドレス
        assert response.status_code == 404  # abortされる

    # ＜エラー系4-4＞
    # ＜売出停止画面の表示＞
    def test_error_4_4(self, app):
        client = self.client_with_admin_login(app)

        # 売出停止処理
        response = client.get(self.url_cancel_order + "0x4444")  # 不正なアドレス
        assert response.status_code == 404  # abortされる

    # ＜エラー系4_5＞
    # ＜所有者移転＞
    #   所有者移転画面の参照：GET　→　何らかの影響で指定したトークンが存在しない
    def test_error_4_5(self, app):
        client = self.client_with_admin_login(app)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])

        # 所有者移転画面の参照
        response = client.get(
            self.url_transfer_ownership + "0x5555" + '/' + issuer_address)  # 不正なアドレス
        assert response.status_code == 404  # abortされる

    # ＜エラー系4-6＞
    # ＜割当（募集申込）＞
    #   割当（募集申込）画面参照：GET　→　何らかの影響で指定したトークンが存在しない
    def test_error_4_6(self, app):
        client = self.client_with_admin_login(app)

        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_allocate + '/' + "0x6666" + '/' + trader_address  # 不正なアドレス
        response = client.get(url)
        assert response.status_code == 404  # abortされる

    # ＜エラー系5_1＞
    #   割当（トークンアドレス形式エラー）
    def test_error_5_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={
                'token_address': "0x1111",  # 不正なアドレス
                'to_address': eth_account['trader']['account_address'],
                'amount': 1
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert 'クーポンアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系5_2＞
    #   割当（割当先アドレス形式エラー）
    def test_error_5_2(self, app):
        token = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).first()

        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={
                'token_address': token.token_address,
                'to_address': "0x2222",  # 不正なアドレス
                'amount': 1
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert '割当先アドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系5_3＞
    #   割当（割当数量上限エラー）
    def test_error_5_3(self, app):
        token = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).first()

        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={
                'token_address': token.token_address,
                'to_address': eth_account['trader']['account_address'],
                'amount': 100_000_001
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert '割当数量は100,000,000が上限です。'.encode('utf-8') in response.data

    # ＜エラー系5_4＞
    #   割当（残高エラー）
    def test_error_5_4(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        token = tokens[1]
        total_supply = 2000000

        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={
                'token_address': token.token_address,
                'to_address': eth_account['trader']['account_address'],
                'amount': total_supply + 1
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert '割当数量が残高を超えています。'.encode('utf-8') in response.data

    # ＜エラー系5_5＞
    #   割当（クーポンアドレスが無効）
    def test_error_5_5(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={
                'token_address': '0xd05029ed7f520ddaf0851f55d72ac8f28ec31823',  # コントラクトが登録されていないアドレス
                'to_address': eth_account['trader']['account_address'],
                'amount': 1
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert '無効なクーポンアドレスです。'.encode('utf-8') in response.data

    # ＜エラー系6_1＞
    # ＜発行体相違＞
    #   トークン追跡: 異なる発行体管理化のトークンアドレス
    def test_error_6_1(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_token_tracker + token.token_address)
        assert response.status_code == 404

    # ＜エラー系6_2＞
    # ＜発行体相違＞
    #   申込者リストCSVダウンロード: 異なる発行体管理化のトークンアドレス
    def test_error_6_2(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_applications_csv_download,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_3＞
    # ＜発行体相違＞
    #   募集申込一覧取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_6_3(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_applications + token.token_address)
        assert response.status_code == 404

    # ＜エラー系6_4＞
    # ＜発行体相違＞
    #   公開: 異なる発行体管理化のトークンアドレス
    def test_error_6_4(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_release,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_5＞
    # ＜発行体相違＞
    #   追加発行: 異なる発行体管理化のトークンアドレス
    def test_error_6_5(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_add_supply + token.token_address)
        assert response.status_code == 404

        response = client.post(
            self.url_add_supply + token.token_address,
            data={
                'addSupply': 1
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_6＞
    # ＜発行体相違＞
    #   設定内容修正: 異なる発行体管理化のトークンアドレス
    def test_error_6_6(self, app, shared_contract):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 404

        response = client.post(
            self.url_setting + token.token_address,
            data={
                'details': 'details詳細2',
                'return_details': 'return詳細2',
                'memo': 'memoメモ2',
                'expirationDate': '20200101',
                'transferable': 'False',
                'tradableExchange': shared_contract['IbetCouponExchange']['address'],
                'image_1': 'https://test.com/image_12.jpg',
                'image_2': 'https://test.com/image_22.jpg',
                'image_3': 'https://test.com/image_32.jpg',
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_7＞
    # ＜発行体相違＞
    #   売出: 異なる発行体管理化のトークンアドレス
    def test_error_6_7(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 404

        response = client.post(
            self.url_sell + token.token_address,
            data={
                'sellPrice': 1000
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_8＞
    # ＜発行体相違＞
    #   売出停止: 異なる発行体管理化のトークンアドレス
    def test_error_6_8(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_cancel_order + token.token_address + '/1')
        assert response.status_code == 404

        response = client.post(
            self.url_cancel_order + token.token_address + '/1',
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_9＞
    # ＜発行体相違＞
    #   割当: 異なる発行体管理化のトークンアドレス
    def test_error_6_9(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_transfer,
            data={
                'token_address': token.token_address,
                'to_address': eth_account['issuer2']['account_address'],
                'amount': 1
            }
        )
        assert response.status_code == 200
        assert '無効なクーポンアドレスです。'.encode('utf-8') in response.data

    # ＜エラー系6_10＞
    # ＜発行体相違＞
    #   割当（募集申込）: 異なる発行体管理化のトークンアドレス
    def test_error_6_10(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')
        account_address = eth_account['trader']['account_address']

        response = client.get(self.url_allocate + token.token_address + '/' + account_address)
        assert response.status_code == 404

        response = client.post(
            self.url_allocate + token.token_address + '/' + account_address,
            data={
                'amount': 1
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_11＞
    # ＜発行体相違＞
    #   保有者移転: 異なる発行体管理化のトークンアドレス
    def test_error_6_11(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')
        account_address = eth_account['trader']['account_address']

        response = client.get(self.url_transfer_ownership + token.token_address + '/' + account_address)
        assert response.status_code == 404

        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + account_address,
            data={
                'amount': 1
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_12＞
    # ＜発行体相違＞
    #   トークン利用履歴取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_6_12(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_usage_history_coupon + token.token_address)
        assert response.status_code == 404

    # ＜エラー系6_13＞
    # ＜発行体相違＞
    #   トークン利用履歴リストCSVダウンロード: 異なる発行体管理化のトークンアドレス
    def test_error_6_13(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_used_csv_download,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_14＞
    # ＜発行体相違＞
    #   保有者一覧取得（CSV）: 異なる発行体管理化のトークンアドレス
    def test_error_6_14(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_holders_csv_download,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_15＞
    # ＜発行体相違＞
    #   保有者一覧取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_6_15(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_holders + token.token_address)
        assert response.status_code == 404

    # ＜エラー系6_16＞
    # ＜発行体相違＞
    #   トークン名称取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_6_16(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_token_name + token.token_address)
        assert response.status_code == 404

    # ＜エラー系6_17＞
    # ＜発行体相違＞
    #   保有者詳細: 異なる発行体管理化のトークンアドレス
    def test_error_6_17(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')
        account_address = eth_account['trader']['account_address']

        response = client.get(self.url_holder + token.token_address + '/' + account_address)
        assert response.status_code == 404

        response = client.post(
            self.url_holder + token.token_address + '/' + account_address,
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_18＞
    # ＜発行体相違＞
    #   有効化: 異なる発行体管理化のトークンアドレス
    def test_error_6_18(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_valid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_19＞
    # ＜発行体相違＞
    #   無効化: 異なる発行体管理化のトークンアドレス
    def test_error_6_19(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_invalid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_20＞
    # ＜発行体相違＞
    #   募集申込開始: 異なる発行体管理化のトークンアドレス
    def test_error_6_20(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_start_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系6_21＞
    # ＜発行体相違＞
    #   募集申込停止: 異なる発行体管理化のトークンアドレス
    def test_error_6_21(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_COUPON,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_stop_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    #############################################################################
    # 後処理
    #############################################################################
    def test_end(self, db):
        clean_issue_event(db)
