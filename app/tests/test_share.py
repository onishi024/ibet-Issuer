# -*- coding:utf-8 -*-
import pytest
import json
import base64
import time
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from app.contracts import Contract
from config import Config
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, index_transfer_event, clean_issue_event
from .utils.contract_utils_share import is_address_authorized
from .utils.contract_utils_personal_info import register_personal_info
from ..models import Token


class TestShare(TestBase):
    #############################################################################
    # テスト対象URL
    #############################################################################
    url_issue = '/share/issue'  # 新規発行
    url_list = '/share/list'  # 発行済一覧
    url_setting = '/share/setting/'  # 詳細設定
    url_release = '/share/release'  # 公開
    url_start_offering = '/share/start_offering'  # 募集申込開始
    url_stop_offering = '/share/stop_offering'  # 募集申込停止
    url_valid = '/share/valid'  # 有効化（取扱開始）
    url_invalid = '/share/invalid'  # 無効化（取扱中止）
    url_change_supply = '/share/change_supply/'  # 発行量変更
    url_add_supply = '/share/add_supply/'  # 追加発行
    url_remove_supply = '/share/remove_supply/'  # 減資
    url_address_authorization = '/share/address_authorization/'  # アドレス認可
    url_authorize_address = '/share/authorize_address/'  # 認可
    url_unauthorize_address = '/share/unauthorize_address/'  # 認可取り消し
    url_tokentrack = '/share/token/track/'  # 追跡
    url_applications = '/share/applications/'  # 募集申込一覧
    url_holders = '/share/holders/'  # 保有者一覧

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
        'cansellationDate': '20200601',
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
        'cansellationDate': '',
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
        'cansellationDate': '20230612',
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
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SHARE)\
            .order_by(Token.created).all()
        return tokens[num]

    #############################################################################
    # 共通処理
    #############################################################################
    @pytest.fixture(scope='class', autouse=True)
    def setup_personal_info(self, shared_contract):
        # PersonalInfo情報の暗号化
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
    #   売出管理画面の参照(0件)
    def test_normal_1_2(self, app):
        # TODO: Test
        pass

    # ＜正常系1_3＞
    # ＜株式の0件確認＞
    #   新規発行画面表示
    def test_normal_1_3(self, app, db, shared_contract):
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

    # ＜正常系2_3＞
    # ＜株式の1件確認＞
    #   売出管理画面の参照(1件)
    def test_normal_2_3(self, app):
        # TODO
        pass

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

    # ＜正常系3_3＞
    # ＜株式一覧（複数件）＞
    #   売出管理画面の参照（複数件）
    def test_normal_3_3(self, app):
        # TODO: Test
        pass

    # ＜正常系4_1＞
    # ＜売出画面＞
    #   新規売出画面の参照
    #   ※Token_1が対象
    def test_normal_4_1(self, app):
        # TODO: Test
        pass

    # ＜正常系5_1＞
    # ＜詳細設定＞
    #   売出　→　詳細設定（設定変更）　→　詳細設定画面参照
    #   ※Token_1が対象、Token_3の状態に変更
    def test_normal_5_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # TODO: 売出し処理

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
        assert str(self.token_data3['cansellationDate']).encode('utf-8') in response.data
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

    # ＜正常系5_2＞
    # ＜詳細設定＞
    #   同じ値で更新処理　→　各値に変更がないこと
    def test_normal_5_2(self, app):
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

    # ＜正常系5_3＞
    # ＜設定画面＞
    #   公開処理　→　公開済状態になること
    #   ※Token_1が対象
    def test_normal_5_3(self, app):
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

    # ＜正常系5_4＞
    # ＜設定画面＞
    #   取扱停止処理　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_4(self, app):
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

    # ＜正常系5_5＞
    # ＜設定画面＞
    #   取扱開始　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_5(self, app):
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

    # ＜正常系5_6＞
    # ＜設定画面＞
    #   減資　→　発行量変更画面参照　→　追加発行　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_6(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_change_supply = self.url_change_supply + token.token_address
        url_add_supply = self.url_add_supply + token.token_address
        url_remove_supply = self.url_remove_supply + token.token_address
        url_setting = self.url_setting + token.token_address

        # 減資
        response = client.post(
            url_remove_supply,
            data={
                'amount': 10,
                'target_address': eth_account['issuer']['account_address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 発行量変更画面の参照
        response = client.get(url_change_supply)
        assert '<title>発行量変更'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply'] - 10).encode('utf-8') in response.data

        # 追加発行画面の参照
        response = client.post(
            url_add_supply,
            data={
                'amount': 10,
                'target_address': eth_account['issuer']['account_address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面の参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply']).encode('utf-8') in response.data

    # ＜正常系5_7＞
    # ＜設定画面＞
    #   追加発行（ロックあり）　→　詳細設定画面参照　→　減資（ロックあり）　→　発行量変更画面で確認
    #   ※Token_1が対象
    def test_normal_5_7(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_change_supply = self.url_change_supply + token.token_address
        url_add_supply = self.url_add_supply + token.token_address
        url_remove_supply = self.url_remove_supply + token.token_address
        url_setting = self.url_setting + token.token_address

        # 追加発行画面の参照
        response = client.post(
            url_add_supply,
            data={
                'amount': 33,
                'target_address': eth_account['issuer']['account_address'],
                'locked_account': eth_account['trader']['account_address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面の参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply'] + 33).encode('utf-8') in response.data

        # 減資
        response = client.post(
            url_remove_supply,
            data={
                'amount': 33,
                'target_address': eth_account['issuer']['account_address'],
                'locked_account': eth_account['trader']['account_address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 発行量変更画面の参照
        response = client.get(url_change_supply)
        assert '<title>発行量変更'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply']).encode('utf-8') in response.data

    # ＜正常系5_8＞
    # ＜設定画面＞
    #   減資（保有量不足でrevert）
    def test_normal_5_8(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_remove_supply = self.url_remove_supply + token.token_address

        # 減資
        response = client.post(
            url_remove_supply,
            data={
                'amount': self.token_data1['totalSupply'] + 1,
                'target_address': eth_account['issuer']['account_address']
            }
        )
        assert response.status_code == 200
        assert '変更量が保有数量を上回っています。'.encode('utf-8') in response.data

    # ＜正常系5_9＞
    # ＜設定画面＞
    #   アドレス認可画面　→　アドレス認可実施
    #   ※Token_1が対象
    def test_normal_5_9(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)
        target_address = eth_account['trader']['account_address']

        # アドレス認可画面
        response = client.get(self.url_address_authorization + token.token_address)
        assert response.status_code == 200
        assert '<title>アドレス認可'.encode('utf-8') in response.data

        # アドレス認可実施
        response = client.post(
            self.url_authorize_address + token.token_address,
            data={
                'token_address': token.token_address,
                "target_address": target_address
            }
        )
        assert response.status_code == 302
        assert is_address_authorized(token, target_address)

    # ＜正常系5_10＞
    # ＜設定画面＞
    #   アドレス認可画面　→　アドレス認可取消
    #   ※Token_1が対象
    def test_normal_5_10(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)
        target_address = eth_account['trader']['account_address']

        # アドレス認可画面
        response = client.get(self.url_address_authorization + token.token_address)
        assert response.status_code == 200
        assert '<title>アドレス認可'.encode('utf-8') in response.data

        # 取扱開始処理
        response = client.post(
            self.url_unauthorize_address + token.token_address,
            data={
                'token_address': token.token_address,
                "target_address": target_address
            }
        )
        assert response.status_code == 302
        assert not is_address_authorized(token, target_address)

    # ＜正常系6_1＞
    # ＜保有者一覧＞
    #   保有者一覧で確認(1件)
    #   ※Token_1が対象
    def test_normal_6_1(self, app, shared_contract):
        # TODO: Test
        pass

    # ＜正常系7_1＞
    # ＜所有者移転＞
    #   所有者移転画面の参照
    #   ※Token_1が対象
    def test_normal_7_1(self, app):
        # TODO: Test
        pass


    # ＜正常系8_1＞
    # ＜募集申込開始・停止＞
    #   初期状態：募集申込停止中（詳細設定画面で確認）
    #   ※Token_1が対象
    def test_normal_8_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>株式詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

    # ＜正常系8_2＞
    # ＜募集申込開始・停止＞
    #   募集申込開始　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_8_2(self, app):
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

    # ＜正常系8_3＞
    # ＜募集申込開始・停止＞
    #   募集申込停止　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_8_3(self, app):
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


    # ＜正常系9_1＞
    # ＜追跡＞
    def test_normal_9_1(self, app):
        # TODO: 保有者移転実装後にテスト
        pass

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
        assert '権利確定日は必須です。'.encode('utf-8') in response.data
        assert '配当支払日は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは必須です。'.encode('utf-8') in response.data

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
    #   追加発行量（アドレス形式エラー）
    def test_error_2_3(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_setting = self.url_add_supply + token.token_address
        response = client.post(
            url_setting,
            data={
                'target_address': error_address,
                'locked_address': error_address,
            }
        )
        assert response.status_code == 200
        assert '保有者アドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
        assert 'ロック者アドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_4＞
    # ＜入力値チェック＞
    #   減資（アドレス形式エラー）
    def test_error_2_4(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_setting = self.url_remove_supply + token.token_address
        response = client.post(
            url_setting,
            data={
                'target_address': error_address,
                'locked_address': error_address,
            }
        )
        assert response.status_code == 200
        assert '保有者アドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
        assert 'ロック者アドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_5＞
    # ＜入力値チェック＞
    #   アドレス認可（アドレス形式エラー）
    def test_error_2_5(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_setting = self.url_authorize_address + token.token_address
        response = client.post(
            url_setting,
            data={
                'target_address': error_address,
            }
        )
        assert response.status_code == 200
        assert '認可コントラクトアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_6＞
    # ＜入力値チェック＞
    #   アドレス認可取消（アドレス形式エラー）
    def test_error_2_6(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_setting = self.url_unauthorize_address + token.token_address
        response = client.post(
            url_setting,
            data={
                'target_address': error_address,
            }
        )
        assert response.status_code == 200
        assert '認可コントラクトアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
