# -*- coding:utf-8 -*-
import base64
import json

import pytest
import time
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from eth_utils import to_checksum_address

from config import Config
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, index_transfer_event, clean_issue_event
from .utils.contract_utils_personal_info import register_personal_info
from .utils.contract_utils_share import create_order, get_latest_orderid, get_latest_agreementid, take_buy, \
    confirm_agreement, apply_for_offering
from ..models import Token


class TestShare(TestBase):
    #############################################################################
    # テスト対象URL
    #############################################################################
    url_get_token_name = '/share/get_token_name/'  # トークン名取得（API）
    url_issue = '/share/issue'  # 新規発行
    url_list = '/share/list'  # 発行済一覧
    url_setting = '/share/setting/'  # 詳細設定
    url_release = '/share/release'  # 公開
    url_start_offering = '/share/start_offering'  # 募集申込開始
    url_stop_offering = '/share/stop_offering'  # 募集申込停止
    url_valid = '/share/valid'  # 有効化（取扱開始）
    url_invalid = '/share/invalid'  # 無効化（取扱中止）
    url_add_supply = '/share/add_supply/'  # 追加発行
    url_applications = '/share/applications/'  # 募集申込一覧
    url_applications_csv_download = '/share/applications_csv_download'  # 申込者リストCSVダウンロード
    url_get_applications = '/share/get_applications/'  # 申込一覧取得
    url_allocate = '/share/allocate/'  # 割当（募集申込）
    url_holders = '/share/holders/'  # 保有者一覧
    url_holders_csv_download = '/share/holders_csv_download'  # 保有者リストCSVダウンロード
    url_get_holders = '/share/get_holders/'  # 保有者一覧取得
    url_transfer_ownership = '/share/transfer_ownership/'  # 保有者移転
    url_holder = '/share/holder/'  # 保有者詳細

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
            # \uff0d: 「－」FULLWIDTH HYPHEN-MINUS。半角ハイフン変換対象。
            # \u30fc: 「ー」KATAKANA-HIRAGANA PROLONGED SOUND MARK。半角ハイフン変換対象外。
            "address1": "勝どき1丁目１\uff0d２\u30fc３",
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
    # テスト用株式トークン情報
    #############################################################################
    # Token_1：最初に新規発行されるトークン。
    token_data1 = {
        'name': 'テスト会社株',
        'symbol': 'SHARE',
        'totalSupply': 1000000,
        'issuePrice': 1000,
        'dividends': 100,
        'dividendRecordDate': '20200401',
        'dividendPaymentDate': '20200501',
        'cancellationDate': '20200601',
        'transferable': 'True',
        'memo': 'メモ1234',
        'referenceUrls_1': 'http://example.com',
        'referenceUrls_2': 'http://image.png',
        'referenceUrls_3': 'http://image3.org/abc',
        'contact_information': '問い合わせ先ABCDEFG',
        'privacy_policy': 'プライバシーポリシーXYZ'
    }
    # Token_2：2番目に発行されるトークン。imageなし, transferable:False
    token_data2 = {
        'name': '2件目株式',
        'symbol': '2KENME',
        'totalSupply': 2000000,
        'issuePrice': 2000,
        'dividends': 20,
        'dividendRecordDate': '20220412',
        'dividendPaymentDate': '20220512',
        'cancellationDate': '',
        'transferable': 'False',
        'memo': '2memo',
        'referenceUrls_1': '',
        'referenceUrls_2': '',
        'referenceUrls_3': '',
        'contact_information': '',
        'privacy_policy': ''
    }
    # Token_3：設定変更用情報
    token_data3 = {
        'name': '3テスト株式',
        'symbol': '3KENME',
        'totalSupply': 3000000,
        'issuePrice': 3000,
        'dividends': 30,
        'dividendRecordDate': '20230412',
        'dividendPaymentDate': '20230512',
        'cancellationDate': '20230612',
        'transferable': 'False',
        'memo': '3memo',
        'referenceUrls_1': 'http://hoge3.co.jp/foo',
        'referenceUrls_2': '',
        'referenceUrls_3': 'http://hoge3.co.jp/bar',
        'contact_information': '3問い合わせ先',
        'privacy_policy': 'プライバシーポリシー3'
    }

    @pytest.fixture(scope='class', autouse=True)
    def prepare_test_data(self, shared_contract):
        # shared_contract fixtureが必要な情報を設定する
        self.token_data1['tradableExchange'] = shared_contract['IbetShareExchange']['address']
        self.token_data1['personalInfoAddress'] = shared_contract['PersonalInfo']['address']

        self.token_data2['tradableExchange'] = shared_contract['IbetShareExchange']['address']
        self.token_data2['personalInfoAddress'] = shared_contract['PersonalInfo']['address']

        self.token_data3['tradableExchange'] = '0x9ba26793217B1780Ee2cF3cAfEb8e0DB10Dda4De'
        self.token_data3['personalInfoAddress'] = '0x7297845b550eb326b31C9a89c1d46a8F78Ff31F5'

    @staticmethod
    def get_token(num):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SHARE) \
            .order_by(Token.created).all()
        return tokens[num]

    #############################################################################
    # 共通処理
    #############################################################################
    @pytest.fixture(scope='class', autouse=True)
    def setup_personal_info(self, shared_contract):
        # PersonalInfo情報の暗号化
        key = RSA.importKey(open('data/rsa/public.pem').read())
        cipher = PKCS1_OAEP.new(key)

        issuer_encrypted_info = \
            base64.encodebytes(
                cipher.encrypt(json.dumps(self.issuer_personal_info_json).encode('utf-8')))

        trader_encrypted_info = \
            base64.encodebytes(
                cipher.encrypt(json.dumps(self.trader_personal_info_json).encode('utf-8')))

        # PersonalInfo情報の登録
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS = \
            shared_contract['IbetShareExchange']['address']
        Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS = shared_contract['PaymentGateway']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        # PersonalInfo登録（発行体：Issuer）
        register_personal_info(
            eth_account['issuer'],
            shared_contract['PersonalInfo'],
            issuer_encrypted_info
        )

        # PersonalInfo登録（投資家：Trader）
        register_personal_info(
            eth_account['trader'],
            shared_contract['PersonalInfo'],
            trader_encrypted_info
        )

    @pytest.fixture(scope='class', autouse=True)
    def clear_db(self, shared_contract, db):
        yield

        # 後処理
        clean_issue_event(db)

    #############################################################################
    # テスト（正常系）
    #############################################################################
    # ＜正常系1_1＞
    # ＜株式の0件確認＞
    #   株式一覧の参照(0件)
    def test_normal_1_1(self, app):
        # 証券一覧
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>株式一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜株式の0件確認＞
    #   新規発行画面表示
    def test_normal_1_2(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 初期表示
        response = client.get(self.url_issue)

        assert response.status_code == 200
        assert '<title>株式新規発行'.encode('utf-8') in response.data

    # ＜正常系2_1＞
    # ＜株式の1件確認＞
    #   新規発行　→　詳細設定画面の参照
    def test_normal_2_1(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data=self.token_data1
        )
        assert response.status_code == 302
        assert response.headers.get('Location').endswith(self.url_list)

        time.sleep(10)

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        token = TestShare.get_token(0)
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        for value in self.token_data1.values():
            assert str(value).encode('utf-8') in response.data
        # セレクトボックスのassert（譲渡制限）
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data

    # ＜正常系2_2＞
    # ＜株式の1件確認＞
    #   株式一覧の参照(1件)
    def test_normal_2_2(self, app):
        token = TestShare.get_token(0)

        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>株式一覧'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系3_1＞
    # ＜株式一覧（複数件）＞
    #   新規発行（画像URLなし）　→　詳細設定画面の参照
    def test_normal_3_1(self, app, db):
        client = self.client_with_admin_login(app)

        # 新規発行（Token_2）
        response = client.post(
            self.url_issue,
            data=self.token_data2
        )
        assert response.status_code == 302

        time.sleep(10)

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        token = TestShare.get_token(1)
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        for value in self.token_data2.values():
            assert str(value).encode('utf-8') in response.data
        # セレクトボックスのassert（譲渡制限）
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data

    # ＜正常系3_2＞
    # ＜株式一覧（複数件）＞
    #   発行済一覧画面の参照（複数件）
    def test_normal_3_2(self, app):
        token1 = TestShare.get_token(0)
        token2 = TestShare.get_token(1)

        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>株式一覧'.encode('utf-8') in response.data

        # Token_1
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token1.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

        # Token_2
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert token2.token_address.encode('utf-8') in response.data

    # ＜正常系4_1＞
    # ＜詳細設定＞
    #   詳細設定（設定変更）　→　詳細設定画面参照
    #   ※Token_1が対象、Token_3の状態に変更
    def test_normal_4_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

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
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data3['dividends']).encode('utf-8') in response.data
        assert str(self.token_data3['dividendRecordDate']).encode('utf-8') in response.data
        assert str(self.token_data3['dividendPaymentDate']).encode('utf-8') in response.data
        assert str(self.token_data3['cancellationDate']).encode('utf-8') in response.data
        # セレクトボックスのassert（譲渡制限）
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert str(self.token_data3['memo']).encode('utf-8') in response.data
        assert str(self.token_data3['referenceUrls_1']).encode('utf-8') in response.data
        assert str(self.token_data3['referenceUrls_2']).encode('utf-8') in response.data
        assert str(self.token_data3['referenceUrls_3']).encode('utf-8') in response.data
        assert str(self.token_data3['tradableExchange']).encode('utf-8') in response.data
        assert str(self.token_data3['personalInfoAddress']).encode('utf-8') in response.data
        assert str(self.token_data3['contact_information']).encode('utf-8') in response.data

        # データ戻し
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data1
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系4_2＞
    # ＜詳細設定＞
    #   同じ値で更新処理　→　各値に変更がないこと
    def test_normal_4_2(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_setting = self.url_setting + token.token_address

        # 詳細設定：設定変更（Token_1　→　Token_1）
        response = client.post(
            url_setting,
            data=self.token_data1
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面の参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        for value in self.token_data1.values():
            assert str(value).encode('utf-8') in response.data
        # セレクトボックスのassert（譲渡制限）
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data
        # 公開済でないことを確認
        assert '公開 <i class="fa fa-exclamation-triangle">'.encode('utf-8') in response.data

    # ＜正常系4_3＞
    # ＜設定画面＞
    #   公開処理　→　公開済状態になること
    #   ※Token_1が対象
    def test_normal_4_3(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

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
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data

    # ＜正常系4_4＞
    # ＜設定画面＞
    #   取扱停止処理　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_4_4(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

        # 取扱停止処理
        response = client.post(
            self.url_invalid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data
        assert '取扱開始'.encode('utf-8') in response.data

        # 発行済一覧画面の参照
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '停止中'.encode('utf-8') in response.data

    # ＜正常系4_5＞
    # ＜設定画面＞
    #   取扱開始　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_4_5(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

        # 取扱開始処理
        response = client.post(
            self.url_valid,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '取扱停止'.encode('utf-8') in response.data

        # 発行済一覧画面の参照
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系4_6＞
    # ＜設定画面＞
    #   追加発行画面参照　→　追加発行処理　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_4_6(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_add_supply = self.url_add_supply + token.token_address

        # 追加発行画面の参照
        response = client.get(url_add_supply)
        assert '<title>追加発行'.encode('utf-8') in response.data

        # 追加発行処理
        response = client.post(
            url_add_supply,
            data={
                'amount': 10,
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply'] + 10).encode('utf-8') in response.data

    # ＜正常系5_1＞
    # ＜保有者一覧＞
    #   保有者一覧で確認(1件)
    #   ※Token_1が対象
    def test_normal_5_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 発行体のpersonalInfo登録
        register_personal_info(
            eth_account['issuer'],
            shared_contract['PersonalInfo'],
            self.issuer_encrypted_info
        )

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>株式保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert eth_account['issuer']['account_address'] == response_data[0]['account_address']
        assert '株式会社１' == response_data[0]['name']
        assert '1234567' == response_data[0]['postal_code']
        assert '東京都中央区　日本橋11-1　東京マンション１０１' == response_data[0]['address']
        assert 'abcd1234@aaa.bbb.cc' == response_data[0]['email']
        assert '20190902' == response_data[0]['birth_date']
        assert 1000010 == response_data[0]['balance']
        assert 0 == response_data[0]['commitment']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert self.token_data1['name'] == response_data

    # ＜正常系5_2＞
    # ＜保有者一覧＞
    #   約定　→　保有者一覧で確認（複数件）
    #   ※Token_1が対象
    def test_normal_5_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 株式の売出
        exchange = shared_contract['IbetShareExchange']
        price = 100
        amount = 20
        create_order(
            eth_account['issuer'],
            eth_account['trader'],
            exchange,
            token.token_address,
            amount,
            price,
            eth_account['agent']
        )

        # 投資家のpersonalInfo登録
        register_personal_info(
            eth_account['trader'],
            shared_contract['PersonalInfo'],
            self.trader_encrypted_info
        )

        # 約定データの作成
        orderid = get_latest_orderid(exchange)
        take_buy(eth_account['trader'], exchange, orderid)
        agreementid = get_latest_agreementid(exchange, orderid)
        confirm_agreement(eth_account['agent'], exchange, orderid, agreementid)

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>株式保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)

        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '株式会社１' == response_data['name']
                assert '1234567' == response_data['postal_code']
                assert '東京都中央区　日本橋11-1　東京マンション１０１' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20190902' == response_data['birth_date']
                assert 999990 == response_data['balance']
                assert 0 == response_data['commitment']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１−２−３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 20 == response_data['balance']
                assert 0 == response_data['commitment']
            else:
                pytest.raises(AssertionError)

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert self.token_data1['name'] == response_data

    # ＜正常系5_3＞
    # ＜保有者一覧＞
    #   保有者詳細
    #   ※Token_1が対象
    def test_normal_5_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 保有者詳細画面の参照
        response = client.get(self.url_holder + token.token_address + '/' + eth_account['issuer']['account_address'])
        assert response.status_code == 200
        assert '<title>株式保有者詳細'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '1234567'.encode('utf-8') in response.data
        assert '東京都'.encode('utf-8') in response.data
        assert '中央区'.encode('utf-8') in response.data
        assert '日本橋11-1'.encode('utf-8') in response.data
        assert '東京マンション１０１'.encode('utf-8') in response.data

    # ＜正常系6_1＞
    # ＜所有者移転＞
    #   所有者移転画面の参照
    #   ※Token_1が対象
    def test_normal_6_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])

        # 所有者移転画面の参照
        response = client.get(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address)
        assert response.status_code == 200
        assert '<title>所有者移転'.encode('utf-8') in response.data
        assert ('value="' + str(issuer_address)).encode('utf-8') in response.data

    # ＜正常系6_2＞
    # ＜所有者移転＞
    #   所有者移転処理　→　保有者一覧の参照
    #   ※Token_1が対象
    def test_normal_6_2(self, app, db):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
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

        # 移転イベントを登録
        index_transfer_event(
            db,
            '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
            token.token_address,
            issuer_address,
            trader_address,
            10
        )

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>株式保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)
        assert response.status_code == 200

        assert len(response_data_list) == 2
        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '株式会社１' == response_data['name']
                assert '1234567' == response_data['postal_code']
                assert '東京都中央区　日本橋11-1　東京マンション１０１' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20190902' == response_data['birth_date']
                assert 999980 == response_data['balance']
                assert 0 == response_data['commitment']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１\uff0d２\u30fc３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 30 == response_data['balance']
                assert 0 == response_data['commitment']
            else:
                pytest.raises(AssertionError)

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert self.token_data1['name'] == response_data

    # ＜正常系6-3＞
    #   保有者リストCSVダウンロード
    def test_normal_6_3(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        payload = {
            'token_address': token.token_address,
        }
        response = client.post(self.url_holders_csv_download, data=payload)
        response_csv = response.data.decode('sjis')

        # CSVヘッダ
        csv_header = ",".join([
            'token_name', 'token_address', 'account_address',
            'balance', 'commitment',
            'name', 'birth_date', 'postal_code', 'address', 'email'
        ])
        # CSVデータ（発行体）
        csv_row_issuer = ','.join([
            self.token_data1['name'], token.token_address, eth_account['issuer']['account_address'],
            '999980', '0',
            '株式会社１', '20190902', '1234567', '東京都中央区　日本橋11-1　東京マンション１０１', 'abcd1234@aaa.bbb.cc'
        ])
        # CSVデータ（投資家）
        csv_row_trader = ','.join([
            self.token_data1['name'], token.token_address, eth_account['trader']['account_address'],
            '30', '0',
            'ﾀﾝﾀｲﾃｽﾄ', '20191102', '1040053', '東京都中央区　勝どき1丁目１\u002d２\u30fc３', 'abcd1234@aaa.bbb.cc'
        ])

        assert response.status_code == 200
        # CSVの出力順は不定なのでinでassertする
        assert csv_header in response_csv
        assert csv_row_issuer in response_csv
        assert csv_row_trader in response_csv

    # ＜正常系7_1＞
    # ＜募集申込開始・停止＞
    #   初期状態：募集申込停止中（詳細設定画面で確認）
    #   ※Token_1が対象
    def test_normal_7_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

    # ＜正常系7_2＞
    # ＜募集申込開始・停止＞
    #   募集申込開始　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_7_2(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 募集申込開始
        response = client.post(
            self.url_start_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '募集申込停止'.encode('utf-8') in response.data

    # ＜正常系7_3＞
    # ＜募集申込開始・停止＞
    #   募集申込停止　→　詳細設定画面で確認
    #   ※TOKEN_1が対象
    def test_normal_7_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 募集申込停止
        response = client.post(
            self.url_stop_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

        # 募集申込状態に戻す
        response = client.post(
            self.url_start_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

    # ＜正常系8_1＞
    # ＜募集申込一覧参照＞
    #   0件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_8_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 募集申込一覧参照
        response = client.get(self.url_applications + str(token.token_address))
        assert response.status_code == 200
        assert '<title>募集申込一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系8_2＞
    # ＜募集申込一覧参照＞
    #   1件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_8_2(self, db, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = token.token_address
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

    # ＜正常系8_3＞
    # ＜募集申込一覧CSVダウンロード＞
    #   1件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_8_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = token.token_address
        trader_address = eth_account['trader']['account_address']

        # 募集申込一覧参照
        response = client.post(
            self.url_applications_csv_download,
            data={
                'token_address': token_address
            }
        )

        assumed_csv = 'token_name,token_address,account_address,name,email,code,requested_amount\n' + \
                      f'{self.token_data1["name"]},{token_address},{trader_address},{self.trader_personal_info_json["name"]},{self.trader_personal_info_json["email"]},abcdefgh,1\n'

        assert response.status_code == 200
        assert assumed_csv.encode('sjis') == response.data

    # ＜正常系9_1＞
    # ＜割当（募集申込）＞
    #   ※8_2の続き
    #   割当（募集申込）画面参照：GET
    #   ※Token_1が対象
    def test_normal_9_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = token.token_address
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_allocate + token_address + '/' + trader_address
        response = client.get(url)
        assert response.status_code == 200
        assert '株式割当'.encode('utf-8') in response.data
        assert token_address.encode('utf-8') in response.data
        assert trader_address.encode('utf-8') in response.data

    # ＜正常系9_2＞
    # ＜割当（募集申込）＞
    #   ※6_2, 8_2の後に実施
    #   割当（募集申込）処理　→　保有者一覧参照
    #   ※Token_1が対象
    def test_normal_9_2(self, db, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = str(token.token_address)
        issuer_address = eth_account['issuer']['account_address']
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_allocate + token_address + '/' + trader_address
        response = client.post(url, data={'amount': 10})
        assert response.status_code == 302

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
        response = client.get(self.url_holders + token_address)
        assert response.status_code == 200
        assert '<title>株式保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200

        # issuer
        assert issuer_address == response_data[0]['account_address']
        assert '株式会社１' == response_data[0]['name']
        assert '1234567' == response_data[0]['postal_code']
        assert '東京都中央区　日本橋11-1　東京マンション１０１' == response_data[0]['address']
        assert 'abcd1234@aaa.bbb.cc' == response_data[0]['email']
        assert '20190902' == response_data[0]['birth_date']
        assert 999970 == response_data[0]['balance']
        assert 0 == response_data[0]['commitment']

        # trader
        assert trader_address == response_data[1]['account_address']
        assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data[1]['name']
        assert '1040053' == response_data[1]['postal_code']
        assert '東京都中央区　勝どき1丁目１－２ー３' == response_data[1]['address']
        assert 'abcd1234@aaa.bbb.cc' == response_data[1]['email']
        assert '20191102' == response_data[1]['birth_date']
        assert 40 == response_data[1]['balance']
        assert 0 == response_data[1]['commitment']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert self.token_data1['name'] == response_data

    #############################################################################
    # テスト（エラー系）
    #############################################################################

    # ＜エラー系1_1＞
    # ＜入力値チェック＞
    #   株式新規発行（必須エラー）
    def test_error_1_1(self, app):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>株式新規発行'.encode('utf-8') in response.data
        assert '名称は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data
        assert '発行価格は必須です。'.encode('utf-8') in response.data
        assert '1口あたりの配当金/分配金は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    # ＜入力値チェック＞
    #   割当（必須エラー）
    def test_error_1_2(self, app):
        client = self.client_with_admin_login(app)
        token = self.get_token(0)
        url_allocate = self.url_allocate + token.token_address + '/' + \
                       eth_account['trader']['account_address']
        # 新規発行
        response = client.post(
            url_allocate,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>株式割当'.encode('utf-8') in response.data
        assert '割当数量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系2_1＞
    # ＜入力値チェック＞
    #   株式新規発行（アドレスのフォーマットエラー）
    def test_error_2_1(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                **self.token_data1,
                'tradableExchange': error_address,
                'personalInfoAddress': error_address,
            }
        )
        assert response.status_code == 200
        assert '<title>株式新規発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_2＞
    # ＜入力値チェック＞
    #   設定画面（アドレス形式エラー）
    def test_error_2_2(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data={
                'tradableExchange': error_address,
                'personalInfoAddress': error_address,
            }
        )
        assert response.status_code == 200
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_3＞
    # ＜入力値チェック＞
    #   割当画面（アドレス形式エラー）
    #     トークンアドレス形式がエラー
    def test_error_2_3(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_allocate = self.url_allocate + error_address + '/' + eth_account['trader']['account_address']
        response = client.post(
            url_allocate,
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系2_4＞
    # ＜入力値チェック＞
    #   割当画面（アドレス形式エラー）
    #     割当先アドレス形式がエラー
    def test_error_2_4(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_allocate = self.url_allocate + token.token_address + '/' + error_address
        response = client.post(
            url_allocate,
            data={
            }
        )
        assert response.status_code == 404

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
        token = TestShare.get_token(0)
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
        token = TestShare.get_token(0)
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
        token = TestShare.get_token(0)
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
        token = TestShare.get_token(0)
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
        token = TestShare.get_token(0)
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

    # ＜エラー系3_7＞
    # ＜割当＞
    #   入力値チェック：amountが残高超
    def test_error_3_7(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_allocate + token.token_address + '/' + issuer_address,
            data={
                'to_address': trader_address,
                'amount': 999991
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data
