# -*- coding:utf-8 -*-
import time
import pytest
import json
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from eth_utils import to_checksum_address

from config import Config
from app.models import Token, Issuer
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, index_transfer_event, clean_issue_event
from .utils.contract_utils_bond import bond_apply_for_offering
from .utils.contract_utils_payment_gateway import register_payment_account
from .utils.contract_utils_personal_info import register_personal_info


class TestBond(TestBase):
    #############################################################################
    # テスト対象URL
    #############################################################################
    url_list = '/bond/list'  # 発行済一覧
    url_positions = '/bond/positions'  # 売出管理
    url_issue = '/bond/issue'  # 新規発行
    url_setting = '/bond/setting/'  # 詳細設定
    url_sell = 'bond/sell/'  # 新規売出
    url_cancel_order = 'bond/cancel_order/'  # 売出停止
    url_release = 'bond/release'  # 公開
    url_holders = 'bond/holders/'  # 保有者一覧
    url_get_holders = 'bond/get_holders/'  # 保有者一覧(API)
    url_holders_csv_download = 'bond/holders_csv_download'  # 保有者リストCSVダウンロード
    url_get_token_name = 'bond/get_token_name/'  # トークン名取得（API）
    url_holder = 'bond/holder/'  # 保有者詳細
    url_signature = 'bond/request_signature/'  # 認定依頼
    url_redeem = 'bond/redeem'  # 償還
    url_transfer_ownership = 'bond/transfer_ownership/'  # 所有者移転
    url_start_initial_offering = 'bond/start_initial_offering'  # 募集申込開始
    url_stop_initial_offering = 'bond/stop_initial_offering'  # 募集申込停止
    url_applications = 'bond/applications/'  # 募集申込一覧
    url_get_applications = 'bond/get_applications/'  # 募集申込一覧
    url_transfer_allotment = 'bond/transfer_allotment'  # 割当（募集申込）

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
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = \
            shared_contract['IbetStraightBondExchange']['address']
        Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS = shared_contract['PaymentGateway']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        # PersonalInfo登録（発行体：Issuer）
        register_personal_info(
            eth_account['issuer'],
            shared_contract['PersonalInfo'],
            self.issuer_encrypted_info
        )

        # PersonalInfo登録（投資家：Trader）
        register_personal_info(
            eth_account['trader'],
            shared_contract['PersonalInfo'],
            self.trader_encrypted_info
        )

        # PaymentGateway：銀行口座情報登録
        register_payment_account(
            eth_account['issuer'],
            shared_contract['PaymentGateway'],
            self.issuer_encrypted_info
        )

        # 発行体名義登録
        issuer = Issuer()
        issuer.eth_account = Config.ETH_ACCOUNT
        issuer.issuer_name = '発行体１'
        db.session.add(issuer)

    # ＜正常系1＞
    #   債券一覧の参照(0件)
    def test_normal_1(self, app):
        # 債券一覧
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>債券一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2＞
    #   債券売出管理(0件)
    def test_normal_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>債券売出管理'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系3＞
    #   新規発行　→　詳細設定画面の参照
    def test_normal_3(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テスト債券',
                'symbol': 'BOND',
                'totalSupply': 1000000,
                'faceValue': 1000,
                'interestRate': 100,
                'interestPaymentDate1': '0101',
                'interestPaymentDate2': '0201',
                'interestPaymentDate3': '0301',
                'interestPaymentDate4': '0401',
                'interestPaymentDate5': '0501',
                'interestPaymentDate6': '0601',
                'interestPaymentDate7': '0701',
                'interestPaymentDate8': '0801',
                'interestPaymentDate9': '0901',
                'interestPaymentDate10': '1001',
                'interestPaymentDate11': '1101',
                'interestPaymentDate12': '1201',
                'redemptionDate': '20191231',
                'redemptionValue': 10000,
                'returnDate': '20191231',
                'returnDetails': '商品券をプレゼント',
                'purpose': '新商品の開発資金として利用。',
                'tradableExchange': shared_contract['IbetStraightBondExchange']['address'],
                'personalInfoAddress': shared_contract['PersonalInfo']['address'],
                'memo': 'メモ'
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '1000000'.encode('utf-8') in response.data
        assert '1000'.encode('utf-8') in response.data
        assert '0101'.encode('utf-8') in response.data
        assert '0201'.encode('utf-8') in response.data
        assert '0301'.encode('utf-8') in response.data
        assert '0401'.encode('utf-8') in response.data
        assert '0501'.encode('utf-8') in response.data
        assert '0601'.encode('utf-8') in response.data
        assert '0701'.encode('utf-8') in response.data
        assert '0801'.encode('utf-8') in response.data
        assert '0901'.encode('utf-8') in response.data
        assert '1001'.encode('utf-8') in response.data
        assert '1101'.encode('utf-8') in response.data
        assert '1201'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '10000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '商品券をプレゼント'.encode('utf-8') in response.data
        assert '新商品の開発資金として利用。'.encode('utf-8') in response.data
        assert shared_contract['IbetStraightBondExchange']['address'].encode('utf-8') in response.data
        assert shared_contract['PersonalInfo']['address'].encode('utf-8') in response.data
        assert 'メモ'.encode('utf-8') in response.data

    # ＜正常系4＞
    #   債券一覧の参照(1件)
    def test_normal_4(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data

    # ＜正常系5＞
    #   売出管理画面の参照(1件)
    def test_normal_5(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>債券売出管理'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data

    # ＜正常系6＞
    #   新規売出画面の参照
    def test_normal_6(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>債券新規売出'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert "{:,}".format(1000000).encode('utf-8') in response.data
        assert "{:,}".format(1000).encode('utf-8') in response.data
        assert '0101'.encode('utf-8') in response.data
        assert '0201'.encode('utf-8') in response.data
        assert '0301'.encode('utf-8') in response.data
        assert '0401'.encode('utf-8') in response.data
        assert '0501'.encode('utf-8') in response.data
        assert '0601'.encode('utf-8') in response.data
        assert '0701'.encode('utf-8') in response.data
        assert '0801'.encode('utf-8') in response.data
        assert '0901'.encode('utf-8') in response.data
        assert '1001'.encode('utf-8') in response.data
        assert '1101'.encode('utf-8') in response.data
        assert '1201'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert "{:,}".format(10000).encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '商品券をプレゼント'.encode('utf-8') in response.data
        assert '新商品の開発資金として利用。'.encode('utf-8') in response.data
        assert shared_contract['IbetStraightBondExchange']['address'].encode('utf-8') in response.data

    # ＜正常系7＞
    #   売出 → 債券売出管理で確認
    def test_normal_7(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        url_sell = self.url_sell + token.token_address

        # 売出
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302

        # 債券売出管理を参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>債券売出管理'.encode('utf-8') in response.data
        assert '新規売出を受け付けました。売出開始までに数分程かかることがあります。'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data

    # ＜正常系8＞
    #   売出停止 → 債券売出管理で確認
    def test_normal_8(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        # 売出停止
        response = client.post(
            self.url_cancel_order + token.token_address + "/1",
        )
        assert response.status_code == 302

        # 債券売出管理を参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>債券売出管理'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data

    # ＜正常系9＞
    #   詳細設定 → 詳細設定画面で確認
    def test_normal_9(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        url_setting = self.url_setting + token.token_address
        client = self.client_with_admin_login(app)

        # 詳細設定
        response = client.post(
            url_setting,
            data={
                'transferable': 'False',  # 初期データから変更登録
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': shared_contract['PaymentGateway']['address'],  # 初期データから変更登録
                'personalInfoAddress': shared_contract['PaymentGateway']['address']  # 初期データから変更登録
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面を参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert 'https://test.com/image_1.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_3.jpg'.encode('utf-8') in response.data
        assert shared_contract['PaymentGateway']['address'].encode('utf-8') in response.data

        # データ戻し
        response = client.post(
            url_setting,
            data={
                'transferable': 'True',
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': shared_contract['IbetStraightBondExchange']['address'],
                'personalInfoAddress': shared_contract['PersonalInfo']['address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系10＞
    #   公開 →　詳細設定画面で確認
    def test_normal_10(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 公開
        response = client.post(
            self.url_release,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(3)

        # 債券詳細設定
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '公開中です。公開開始までに数分程かかることがあります。'.encode('utf-8') in response.data

    # ＜正常系11-1＞
    #   債券保有者一覧
    def test_normal_11_1(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>債券保有者一覧'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data

    # ＜正常系11-2＞
    #   債券保有者一覧(API)
    def test_normal_11_2(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert eth_account['issuer']['account_address'] == response_data[0]['account_address']
        assert '発行体１' == response_data[0]['name']
        assert '--' == response_data[0]['postal_code']
        assert '--' == response_data[0]['address']
        assert '--' == response_data[0]['email']
        assert '--' == response_data[0]['birth_date']
        assert 1000000 == response_data[0]['balance']
        assert 0 == response_data[0]['commitment']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert 'テスト債券' == response_data

    # ＜正常系11-3＞
    #   保有者リストCSVダウンロード
    def test_normal_11_3(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        payload = {
            'token_address': token.token_address,
        }
        response = client.post(self.url_holders_csv_download, data=payload)
        response_csv = response.data.decode('sjis')

        assumed_csv = '\n'.join([
            # CSVヘッダ
            ",".join([
                'token_name', 'token_address', 'account_address',
                'balance', 'commitment', 'total_balance', 'total_holdings',
                'name', 'birth_date', 'postal_code', 'address', 'email'
            ]),
            # CSVデータ
            ','.join([
                'テスト債券', token.token_address, eth_account['issuer']['account_address'],
                '1000000', '0', '1000000', '1000000000',
                '発行体１', '--', '--', '--', '--'
            ])
        ]) + '\n'

        assert response.status_code == 200
        assert response_csv == assumed_csv

    # ＜正常系12＞
    #   債券保有者詳細
    def test_normal_12(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 保有者詳細の参照
        response = client.get(self.url_holder + token.token_address + '/' + eth_account['issuer']['account_address'])
        assert response.status_code == 200
        assert '<title>債券保有者詳細'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '1234567'.encode('utf-8') in response.data
        assert '東京都'.encode('utf-8') in response.data
        assert '中央区'.encode('utf-8') in response.data
        assert '日本橋11-1'.encode('utf-8') in response.data
        assert '東京マンション１０１'.encode('utf-8') in response.data

    # ＜正常系13＞
    #   認定依頼
    def test_normal_13(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)

        # 認定画面（GET）
        response = client.get(url_signature)
        assert response.status_code == 200
        assert '<title>認定依頼'.encode('utf-8') in response.data

        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
                'signer': eth_account['agent']['account_address']
            }
        )
        assert response.status_code == 302

        # 債券詳細設定画面を参照
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '認定依頼を受け付けました。'.encode('utf-8') in response.data

    # ＜正常系14_1＞
    # ＜募集申込開始・停止＞
    #   初期状態：募集申込停止中（詳細設定画面で確認）
    def test_normal_14_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

    # ＜正常系14_2＞
    # ＜募集申込開始・停止＞
    #   募集申込開始　→　詳細設定画面で確認
    def test_normal_14_2(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        # 募集申込開始
        response = client.post(
            self.url_start_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(3)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '募集申込停止'.encode('utf-8') in response.data

    # ＜正常系14_3＞
    # ＜募集申込開始・停止＞
    #   募集申込停止　→　詳細設定画面で確認
    def test_normal_14_3(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

        # 募集申込状態に戻す
        response = client.post(
            self.url_start_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

    # ＜正常系15_1＞
    # ＜募集申込一覧参照＞
    #   0件：募集申込一覧
    def test_normal_15_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        # 募集申込一覧参照
        response = client.get(self.url_applications + str(token.token_address))
        assert response.status_code == 200
        assert '<title>募集申込一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系15_2＞
    # ＜募集申込一覧参照＞
    #   1件：募集申込一覧
    def test_normal_15_2(self, db, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        token_address = str(token.token_address)
        trader_address = eth_account['trader']['account_address']

        # 募集申込データの作成：投資家
        bond_apply_for_offering(
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

    # ＜正常系16＞
    #   償還実施　→　債券一覧で確認
    def test_normal_16(self, app):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_redeem,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302
        time.sleep(3)

        # 債券一覧を参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '償還済'.encode('utf-8') in response.data

    # ＜正常系17_1＞
    # ＜所有者移転＞
    #   所有者移転画面の参照
    def test_normal_17_1(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])

        # 所有者移転画面の参照
        response = client.get(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address)
        assert response.status_code == 200
        assert '<title>所有者移転'.encode('utf-8') in response.data
        assert ('value="' + str(issuer_address)).encode('utf-8') in response.data

    # ＜正常系17_2＞
    # ＜所有者移転＞
    #   所有者移転処理　→　保有者一覧の参照
    def test_normal_17_2(self, db, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        issuer_address = to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
            data={
                'to_address': trader_address,
                'amount': 10
            }
        )
        assert response.status_code == 302  # 処理内でSleep

        # Transferイベント登録
        index_transfer_event(
            db,
            '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
            token.token_address,
            issuer_address,
            trader_address,
            10
        )

        # 保有者一覧の参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)

        assert response.status_code == 200
        count = 0
        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '発行体１' == response_data['name']
                assert '--' == response_data['postal_code']
                assert '--' == response_data['address']
                assert '--' == response_data['email']
                assert '--' == response_data['birth_date']
                assert 999990 == response_data['balance']
                assert 0 == response_data['commitment']
                count += 1
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１－２ー３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 10 == response_data['balance']
                assert 0 == response_data['commitment']
                count += 1
            else:
                pytest.raises(AssertionError)
        assert count == 2

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert 'テスト債券' == response_data

    #############################################################################
    # テスト（エラー系）
    #############################################################################

    # ＜エラー系1＞
    #   債券新規発行（必須エラー）
    def test_error_1(self, app):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>債券新規発行'.encode('utf-8') in response.data
        assert '名称は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data
        assert '発行目的は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系1＞
    #   債券新規発行（DEXアドレスのフォーマットエラー）
    def test_error_1_2(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テスト債券',
                'symbol': 'BOND',
                'totalSupply': 1000000,
                'faceValue': 1000,
                'interestRate': 100,
                'interestPaymentDate1': '0101',
                'interestPaymentDate2': '0201',
                'interestPaymentDate3': '0301',
                'interestPaymentDate4': '0401',
                'interestPaymentDate5': '0501',
                'interestPaymentDate6': '0601',
                'interestPaymentDate7': '0701',
                'interestPaymentDate8': '0801',
                'interestPaymentDate9': '0901',
                'interestPaymentDate10': '1001',
                'interestPaymentDate11': '1101',
                'interestPaymentDate12': '1201',
                'redemptionDate': '20191231',
                'redemptionValue': 10000,
                'returnDate': '20191231',
                'returnDetails': '商品券をプレゼント',
                'purpose': '新商品の開発資金として利用。',
                'tradableExchange': error_address,
                'personalInfoAddress': error_address,
                'memo': 'メモ'
            }
        )
        assert response.status_code == 200
        assert '<title>債券新規発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系1＞
    #   設定画面（DEXアドレスのフォーマットエラー）
    def test_error_1_3(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        # 売出設定
        token = Token.query.get(1)
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data={
                'tradableExchange': error_address
            }
        )
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2＞
    #   売出（必須エラー）
    def test_error_2(self, app):
        token = Token.query.get(1)
        # 売出
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_sell + token.token_address,
            data={
            }
        )
        assert response.status_code == 302
        # 債券新規売出でエラーを確認
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>債券新規売出'.encode('utf-8') in response.data
        assert '売出価格は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3＞
    #   認定（必須エラー）
    def test_error_3(self, app):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)
        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
            }

        )
        assert response.status_code == 200
        assert '認定者は必須です。'.encode('utf-8') in response.data

    # ＜エラー系4＞
    #   認定（認定依頼先アドレスのフォーマットエラー）
    def test_error_4(self, app):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)
        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
                'signer': '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'  # 1桁多い
            }
        )
        assert response.status_code == 200
        assert '有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系5＞
    #   認定（認定依頼がすでに登録されている）
    def test_error_5(self, app):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)
        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
                'signer': eth_account['agent']['account_address']
            }
        )
        assert response.status_code == 200
        assert '既に情報が登録されています。'.encode('utf-8') in response.data

    # ＜エラー系6_1＞
    # ＜所有者移転＞
    #   URLパラメータチェック：token_addressが無効
    def test_error_6_1(self, app):
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

    # ＜エラー系6_2＞
    # ＜所有者移転＞
    #    URLパラメータチェック：account_addressが無効
    def test_error_6_2(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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

    # ＜エラー系6_3＞
    # ＜所有者移転＞
    #   入力値チェック：必須チェック
    def test_error_6_3(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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

    # ＜エラー系6_4＞
    # ＜所有者移転＞
    #   入力値チェック：to_addressが無効
    def test_error_6_4(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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

    # ＜エラー系6_5＞
    # ＜所有者移転＞
    #   入力値チェック：amountが上限超過
    def test_error_6_5(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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

    # ＜エラー系6_6＞
    # ＜所有者移転＞
    #   入力値チェック：amountが残高超
    def test_error_6_6(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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
                'amount': 1000001
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data

    #############################################################################
    # 後処理
    #############################################################################
    def test_end(self, db):
        clean_issue_event(db)

        Issuer.query.filter(Issuer.eth_account == Config.ETH_ACCOUNT).delete()
