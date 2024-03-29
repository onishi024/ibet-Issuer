"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""
import base64
import json
from datetime import (
    datetime,
    timezone
)

import pytest
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from eth_utils import to_checksum_address

from config import Config
from app.models import (
    Token,
    HolderList
)
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import (
    processor_issue_event,
    index_transfer_event,
    clean_issue_event
)
from .utils.contract_utils_personal_info import register_personal_info
from .utils.contract_utils_share import (
    create_order,
    get_latest_orderid,
    get_latest_agreementid,
    take_buy,
    confirm_agreement,
    apply_for_offering
)


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
    url_token_tracker = 'share/token_tracker/'  # トークン追跡
    url_applications = '/share/applications/'  # 募集申込一覧
    url_applications_csv_download = '/share/applications_csv_download'  # 申込者リストCSVダウンロード
    url_get_applications = '/share/get_applications/'  # 申込一覧取得
    url_allot = '/share/allot/'  # 割当登録
    url_transfer_allotment = '/share/transfer_allotment/'  # 割当（募集申込）
    url_holders = '/share/holders/'  # 保有者一覧
    url_holders_csv_download = '/share/holders_csv_download'  # 保有者リストCSVダウンロード
    url_get_holders = '/share/get_holders/'  # 保有者一覧取得
    url_transfer_ownership = '/share/transfer_ownership/'  # 保有者移転
    url_holder = '/share/holder/'  # 保有者詳細
    url_holders_csv_history = 'share/holders_csv_history/'  # 保有者リスト履歴
    url_get_holders_csv_history = 'share/get_holders_csv_history/'  # 保有者リスト履歴（API）
    url_holders_csv_history_download = 'share/holders_csv_history_download'  # 保有者リストCSVダウンロード

    #############################################################################
    # PersonalInfo情報の暗号化
    #############################################################################
    issuer_personal_info_json = {
        "name": "株式会社１",
        "postal_code": "1234567",
        "address": "東京都中央区　日本橋11-1　東京マンション１０１",
        "email": "abcd1234@aaa.bbb.cc",
        "birth": "20190902"
    }

    # \uff0d: 「－」FULLWIDTH HYPHEN-MINUS。半角ハイフン変換対象。
    # \u30fc: 「ー」KATAKANA-HIRAGANA PROLONGED SOUND MARK。半角ハイフン変換対象外。
    trader_personal_info_json = {
        "key_manager": "4010001203704",
        "name": "ﾀﾝﾀｲﾃｽﾄ",
        "postal_code": "1040053",
        "address": "東京都中央区　勝どき1丁目１\uff0d２\u30fc３",
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
    # テスト用トークン情報
    #############################################################################
    # Token_1：最初に新規発行されるトークン。
    token_data1 = {
        'name': 'テスト会社株',
        'symbol': 'SHARE',
        'totalSupply': 1000000,
        'issuePrice': 1000,
        'principalValue': 1000,
        'dividends': 100.25,
        'dividendRecordDate': '20200401',
        'dividendPaymentDate': '20200501',
        'cancellationDate': '20200601',
        'transferable': 'True',
        'transferApprovalRequired': 'False',
        'memo': 'メモ1234',
        'referenceUrls_1': 'http://example.com',
        'referenceUrls_2': 'http://image.png',
        'referenceUrls_3': 'http://image3.org/abc',
        'contact_information': '問い合わせ先ABCDEFG',
        'privacy_policy': 'プライバシーポリシーXYZ'
    }
    # Token_2：2番目に発行されるトークン。
    # 必須項目のみ, transferable:False, transferApprovalRequired:True
    token_data2 = {
        'name': '2件目株式',
        'symbol': '2KENME',
        'totalSupply': 2000000,
        'issuePrice': 2000,
        'principalValue': 1000,
        'dividends': '',
        'dividendRecordDate': '',
        'dividendPaymentDate': '',
        'cancellationDate': '',
        'transferable': 'False',
        'transferApprovalRequired': 'True',
        'memo': '',
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
        'principalValue': 3000,
        'dividends': 30.75,
        'dividendRecordDate': '20230412',
        'dividendPaymentDate': '20230512',
        'cancellationDate': '20230612',
        'transferable': 'False',
        'transferApprovalRequired': 'True',
        'memo': '3memo',
        'referenceUrls_1': 'http://hoge3.co.jp/foo',
        'referenceUrls_2': '',
        'referenceUrls_3': 'http://hoge3.co.jp/bar',
        'contact_information': '3問い合わせ先',
        'privacy_policy': 'プライバシーポリシー3'
    }

    @pytest.fixture(scope='class', autouse=True)
    def prepare_test_data(self, shared_contract, db):
        # shared_contract fixtureが必要な情報を設定する
        self.token_data1['tradableExchange'] = shared_contract['IbetShareExchange']['address']
        self.token_data1['personalInfoAddress'] = shared_contract['PersonalInfo']['address']

        self.token_data2['tradableExchange'] = shared_contract['IbetShareExchange']['address']
        self.token_data2['personalInfoAddress'] = shared_contract['PersonalInfo']['address']

        self.token_data3['tradableExchange'] = '0x9ba26793217B1780Ee2cF3cAfEb8e0DB10Dda4De'
        self.token_data3['personalInfoAddress'] = '0x7297845b550eb326b31C9a89c1d46a8F78Ff31F5'

    @staticmethod
    def get_token(num):
        tokens = Token.query.filter_by(
            admin_address=eth_account['issuer']['account_address'].lower(),
            template_id=Config.TEMPLATE_ID_SHARE
        ).order_by(Token.created).all()
        return tokens[num]

    #############################################################################
    # 共通処理
    #############################################################################
    @pytest.fixture(scope='class', autouse=True)
    def setup_personal_info(self, shared_contract, db):
        # PersonalInfo登録（発行体：Issuer）
        register_personal_info(
            db=db,
            invoker=eth_account['issuer'],
            contract_address=shared_contract['PersonalInfo']['address'],
            info=self.issuer_personal_info_json,
            encrypted_info=self.issuer_encrypted_info
        )

        # PersonalInfo登録（投資家：Trader）
        register_personal_info(
            db=db,
            invoker=eth_account["trader"],
            contract_address=shared_contract["PersonalInfo"]["address"],
            info=self.trader_personal_info_json,
            encrypted_info=self.trader_encrypted_info
        )

    #############################################################################
    # テスト（正常系）
    #############################################################################
    # ＜正常系1_1＞
    # ＜トークンの0件確認＞
    #   トークン一覧の参照(0件)
    def test_normal_1_1(self, app):
        # 証券一覧
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>発行済一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜トークンの0件確認＞
    #   新規発行画面表示
    def test_normal_1_2(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 初期表示
        response = client.get(self.url_issue)

        assert response.status_code == 200
        assert '<title>新規発行'.encode('utf-8') in response.data

    # ＜正常系2_1＞
    # ＜トークンの1件確認＞
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

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        token = TestShare.get_token(0)
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        for value in self.token_data1.values():
            assert str(value).encode('utf-8') in response.data
        # セレクトボックスのassert（譲渡制限）
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data

    # ＜正常系2_2＞
    # ＜トークンの1件確認＞
    #   トークン一覧の参照(1件)
    def test_normal_2_2(self, app):
        token = TestShare.get_token(0)

        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>発行済一覧'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系3_1＞
    # ＜トークン一覧（複数件）＞
    #   新規発行（必須項目のみ）　→　詳細設定画面の参照
    def test_normal_3_1(self, app, db):
        client = self.client_with_admin_login(app)

        # 新規発行（Token_2）
        response = client.post(
            self.url_issue,
            data=self.token_data2
        )
        assert response.status_code == 302

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        token = TestShare.get_token(1)
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        for value in self.token_data2.values():
            if value != '':
                assert str(value).encode('utf-8') in response.data
        # 未設定項目のassert
        assert 'name="dividends" type="text" value="0.00"'.encode('utf-8') in response.data
        assert 'name="dividendRecordDate" type="text" value=""'.encode('utf-8') in response.data
        assert 'name="dividendPaymentDate" type="text" value=""'.encode('utf-8') in response.data
        assert 'name="cancellationDate" type="text" value=""'.encode('utf-8') in response.data
        assert 'id="memo" name="memo"></textarea>'.encode('utf-8') in response.data
        assert 'name="referenceUrls_1" type="text" value=""'.encode('utf-8') in response.data
        assert 'name="referenceUrls_2" type="text" value=""'.encode('utf-8') in response.data
        assert 'name="referenceUrls_3" type="text" value=""'.encode('utf-8') in response.data
        assert 'id="contact_information" name="contact_information"></textarea>'.encode('utf-8') in response.data
        assert 'id="privacy_policy" name="privacy_policy"></textarea>'.encode('utf-8') in response.data
        # セレクトボックスのassert（譲渡制限）
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data

    # ＜正常系3_2＞
    # ＜トークン一覧（複数件）＞
    #   発行済一覧画面の参照（複数件）
    def test_normal_3_2(self, app):
        token1 = TestShare.get_token(0)
        token2 = TestShare.get_token(1)

        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>発行済一覧'.encode('utf-8') in response.data

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

        # 詳細設定画面の参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
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

        # 詳細設定画面の参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
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
        assert '<title>詳細設定'.encode('utf-8') in response.data
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
        assert '<title>詳細設定'.encode('utf-8') in response.data
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
        assert '<title>詳細設定'.encode('utf-8') in response.data
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

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply'] + 10).encode('utf-8') in response.data

    # ＜正常系5_1＞
    # ＜保有者一覧＞
    #   保有者一覧で確認(1件)
    #   ※Token_1が対象
    def test_normal_5_1(self, app, shared_contract, db):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # 発行体のpersonalInfo登録
        register_personal_info(
            db=db,
            invoker=eth_account['issuer'],
            contract_address=shared_contract['PersonalInfo']['address'],
            info=self.issuer_personal_info_json,
            encrypted_info=self.issuer_encrypted_info
        )

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert eth_account['issuer']['account_address'] == response_data['data'][0]['account_address']
        assert '発行体１' == response_data['data'][0]['name']
        assert '--' == response_data['data'][0]['postal_code']
        assert '--' == response_data['data'][0]['address']
        assert '--' == response_data['data'][0]['email']
        assert '--' == response_data['data'][0]['birth_date']
        assert 1000010 == response_data['data'][0]['balance']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert self.token_data1['name'] == response_data

    # ＜正常系5_2＞
    # ＜保有者一覧＞
    #   約定　→　保有者一覧で確認（複数件）
    #   ※Token_1が対象
    def test_normal_5_2(self, app, shared_contract, db):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)

        # トークンの売出
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
            db=db,
            invoker=eth_account["trader"],
            contract_address=shared_contract["PersonalInfo"]["address"],
            info=self.trader_personal_info_json,
            encrypted_info=self.trader_encrypted_info
        )

        # 約定データの作成
        orderid = get_latest_orderid(exchange)
        take_buy(eth_account['trader'], exchange, orderid)
        agreementid = get_latest_agreementid(exchange, orderid)
        confirm_agreement(eth_account['agent'], exchange, orderid, agreementid)

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)['data']

        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '発行体１' == response_data['name']
                assert '--' == response_data['postal_code']
                assert '--' == response_data['address']
                assert '--' == response_data['email']
                assert '--' == response_data['birth_date']
                assert 999990 == response_data['balance']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１−２−３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 20 == response_data['balance']
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
        assert '<title>保有者詳細'.encode('utf-8') in response.data
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
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)['data']
        assert response.status_code == 200

        assert len(response_data_list) == 2
        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '発行体１' == response_data['name']
                assert '--' == response_data['postal_code']
                assert '--' == response_data['address']
                assert '--' == response_data['email']
                assert '--' == response_data['birth_date']
                assert 999980 == response_data['balance']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１\uff0d２\u30fc３' == response_data['address']
                assert 'abcd1234@aaa.bbb.cc' == response_data['email']
                assert '20191102' == response_data['birth_date']
                assert 30 == response_data['balance']
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
            'token_name', 'token_address', 'account_address', 'key_manager',
            'balance',
            'name', 'birth_date', 'postal_code', 'address', 'email'
        ])
        # CSVデータ（発行体）
        csv_row_issuer = ','.join([
            self.token_data1['name'], token.token_address, eth_account['issuer']['account_address'], '--',
            '999980',
            '発行体１', '--', '--', '--', '--'
        ])
        # CSVデータ（投資家）
        csv_row_trader = ','.join([
            self.token_data1['name'], token.token_address, eth_account['trader']['account_address'], '4010001203704',
            '30',
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
        assert '<title>詳細設定'.encode('utf-8') in response.data
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
        assert '<title>詳細設定'.encode('utf-8') in response.data
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
        assert '<title>詳細設定'.encode('utf-8') in response.data
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
    # ＜割当登録＞
    #   ※8_2の続き
    #   割当登録画面参照：GET
    #   ※Token_1が対象
    def test_normal_9_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = token.token_address
        trader_address = eth_account['trader']['account_address']

        # 割当登録
        url = self.url_allot + token_address + '/' + trader_address
        response = client.get(url)
        assert response.status_code == 200
        assert '割当登録'.encode('utf-8') in response.data
        assert token_address.encode('utf-8') in response.data
        assert trader_address.encode('utf-8') in response.data

    # ＜正常系9_2＞
    # ＜割当登録＞
    #   ※8_2の後に実施
    #   割当（募集申込）処理　→　保有者一覧参照
    #   ※Token_1が対象
    def test_normal_9_2(self, db, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = str(token.token_address)
        trader_address = eth_account['trader']['account_address']

        # 割当登録
        url = self.url_allot + token_address + '/' + trader_address
        response = client.post(url, data={'amount': 10})
        assert response.status_code == 302

    # ＜正常系10_1＞
    # ＜割当（募集申込）＞
    #   ※9_2の続き
    #   割当（募集申込）画面参照：GET
    #   ※Token_1が対象
    def test_normal_10_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = token.token_address
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_transfer_allotment + token_address + '/' + trader_address
        response = client.get(url)
        assert response.status_code == 200
        assert '権利移転（募集申込）'.encode('utf-8') in response.data
        assert token_address.encode('utf-8') in response.data
        assert trader_address.encode('utf-8') in response.data
        assert "10".encode('utf-8') in response.data  # NOTE:事前に登録した割当数量

    # ＜正常系10_2＞
    # ＜割当（募集申込）＞
    #   ※9_2の後に実施
    #   割当（募集申込）処理　→　保有者一覧参照
    #   ※Token_1が対象
    def test_normal_10_2(self, db, app):
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        token_address = str(token.token_address)
        issuer_address = eth_account['issuer']['account_address']
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_transfer_allotment + token_address + '/' + trader_address
        response = client.post(url)
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
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data = json.loads(response.data)['data']
        assert response.status_code == 200

        # issuer
        assert issuer_address == response_data[0]['account_address']
        assert '発行体１' == response_data[0]['name']
        assert '--' == response_data[0]['postal_code']
        assert '--' == response_data[0]['address']
        assert '--' == response_data[0]['email']
        assert '--' == response_data[0]['birth_date']
        assert 999970 == response_data[0]['balance']

        # trader
        assert trader_address == response_data[1]['account_address']
        assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data[1]['name']
        assert '1040053' == response_data[1]['postal_code']
        assert '東京都中央区　勝どき1丁目１－２ー３' == response_data[1]['address']
        assert 'abcd1234@aaa.bbb.cc' == response_data[1]['email']
        assert '20191102' == response_data[1]['birth_date']
        assert 40 == response_data[1]['balance']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert self.token_data1['name'] == response_data

    # ＜正常系11-1＞
    #   保有者リスト履歴
    def test_normal_11_1(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        response = client.get(self.url_holders_csv_history + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者リスト履歴'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data

    # ＜正常系11-2＞
    #   保有者リスト履歴（API）
    #   0件：保有者リスト履歴
    def test_normal_11_2(self, app):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者一覧（API）の参照
        response = client.get(self.url_get_holders_csv_history + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert len(response_data) == 0

    # ＜正常系11-3＞
    #   保有者リスト履歴（API）
    #   1件：保有者リスト履歴
    def test_normal_11_3(self, app, db):
        token = TestShare.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者リスト履歴を作成
        holderList = HolderList()
        holderList.token_address = token.token_address
        holderList.created = datetime(2020, 2, 29, 12, 59, 59, 1234, tzinfo=timezone.utc)
        holderList.holder_list = b'dummy csv share test_normal_11_3'
        db.session.add(holderList)

        # 保有者一覧（API）の参照
        response = client.get(self.url_get_holders_csv_history + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert len(response_data) == 1
        assert token.token_address == response_data[0]['token_address']
        assert '2020/02/29 21:59:59 +0900' == response_data[0]['created']
        assert '20200229215959share_holders_list.csv' == response_data[0]['file_name']

    # ＜正常系11-4＞
    #   保有者リストCSVダウンロード
    #   ※11-3の続き
    def test_normal_11_4(self, app, db):
        token = TestShare.get_token(0)

        holder_list = HolderList.query.filter_by(token_address=token.token_address).first()
        csv_id = holder_list.id

        client = self.client_with_admin_login(app)

        # 保有者一覧（API）の参照
        response = client.post(
            self.url_holders_csv_history_download,
            data={
                'token_address': token.token_address,
                'csv_id': csv_id
            }
        )

        assert response.status_code == 200
        assert response.data == b'dummy csv share test_normal_11_3'

    #############################################################################
    # テスト（エラー系）
    #############################################################################

    # ＜エラー系1_1＞
    # ＜入力値チェック＞
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
        assert '<title>新規発行'.encode('utf-8') in response.data
        assert '名称は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data
        assert '発行価格は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    # ＜入力値チェック＞
    #   割当（必須エラー）
    def test_error_1_2(self, app):
        client = self.client_with_admin_login(app)
        token = self.get_token(0)
        url_allot = self.url_allot + token.token_address + '/' + \
                    eth_account['trader']['account_address']
        # 新規発行
        response = client.post(
            url_allot,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>割当登録'.encode('utf-8') in response.data
        assert '割当数量を入力してください。'.encode('utf-8') in response.data

    # ＜エラー系2_1＞
    # ＜入力値チェック＞
    #   新規発行（アドレスのフォーマットエラー）
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
        assert '<title>新規発行'.encode('utf-8') in response.data
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
    #   割当登録画面（アドレス形式エラー）
    #     トークンアドレス形式がエラー
    def test_error_2_3(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        url_allocate = self.url_allot + error_address + '/' + eth_account['trader']['account_address']
        response = client.post(
            url_allocate,
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系2_4＞
    # ＜入力値チェック＞
    #   割当登録画面（アドレス形式エラー）
    #     割当先アドレス形式がエラー
    def test_error_2_4(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_allocate = self.url_allot + token.token_address + '/' + error_address
        response = client.post(
            url_allocate,
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系2_5＞
    # ＜入力値チェック＞
    #   権利移転（募集申込）（アドレス形式エラー）
    #     トークンアドレス形式がエラー
    def test_error_2_5(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        url_transfer_allotment = self.url_transfer_allotment + error_address + '/' + eth_account['trader'][
            'account_address']
        response = client.post(
            url_transfer_allotment,
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系2_6＞
    # ＜入力値チェック＞
    #   割当登録画面（アドレス形式エラー）
    #     割当先アドレス形式がエラー
    def test_error_2_6(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestShare.get_token(0)
        url_transfer_allotment = self.url_transfer_allotment + token.token_address + '/' + error_address
        response = client.post(
            url_transfer_allotment,
            data={
            }
        )
        assert response.status_code == 404

    # ＜エラー系2_7＞
    # ＜入力値チェック＞
    #   保有者リスト履歴（アドレスのフォーマットエラー）
    def test_error_2_7(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        response = client.get(self.url_holders_csv_history + error_address)
        assert response.status_code == 404

    # ＜エラー系2_8＞
    #   保有者リスト履歴（API）（アドレスのフォーマットエラー）
    def test_error_2_8(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        response = client.get(self.url_get_holders_csv_history + error_address)
        assert response.status_code == 404

    # ＜エラー系2_9＞
    #   保有者リストCSVダウンロード（アドレスのフォーマットエラー）
    def test_error_2_9(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_holders_csv_history_download,
            data={
                'token_address': error_address,
                'csv_id': 1
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

        # 割当登録
        url = self.url_allot + token.token_address + '/' + issuer_address
        client.post(url, data={'amount': 999991})

        # 所有者移転
        response = client.post(
            self.url_transfer_allotment + token.token_address + '/' + issuer_address,
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data

    # ＜エラー系4_1＞
    # ＜発行体相違＞
    #   トークン追跡: 異なる発行体管理化のトークンアドレス
    def test_error_4_1(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_token_tracker + token.token_address)
        assert response.status_code == 404

    # ＜エラー系4_2＞
    # ＜発行体相違＞
    #   申込者リストCSVダウンロード: 異なる発行体管理化のトークンアドレス
    def test_error_4_2(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_3＞
    # ＜発行体相違＞
    #   募集申込一覧取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_3(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_applications + token.token_address)
        assert response.status_code == 404

    # ＜エラー系4_4＞
    # ＜発行体相違＞
    #   公開: 異なる発行体管理化のトークンアドレス
    def test_error_4_4(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_5＞
    # ＜発行体相違＞
    #   追加発行: 異なる発行体管理化のトークンアドレス
    def test_error_4_5(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_6＞
    # ＜発行体相違＞
    #   設定内容修正: 異なる発行体管理化のトークンアドレス
    def test_error_4_6(self, app, shared_contract):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 404

        response = client.post(
            self.url_setting + token.token_address,
            data=self.token_data1
        )
        assert response.status_code == 404

    # ＜エラー系4_7＞
    # ＜発行体相違＞
    #   権利移転（募集申込）: 異なる発行体管理化のトークンアドレス
    def test_error_4_7(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')
        account_address = eth_account['trader']['account_address']

        response = client.get(self.url_transfer_allotment + token.token_address + '/' + account_address)
        assert response.status_code == 404

        response = client.post(
            self.url_transfer_allotment + token.token_address + '/' + account_address,
            data={
                'amount': 1
            }
        )
        assert response.status_code == 404

    # ＜エラー系4_8＞
    # ＜発行体相違＞
    #   保有者移転: 異なる発行体管理化のトークンアドレス
    def test_error_4_8(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_9＞
    # ＜発行体相違＞
    #   保有者一覧取得（CSV）: 異なる発行体管理化のトークンアドレス
    def test_error_4_9(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_10＞
    # ＜発行体相違＞
    #   保有者一覧取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_10(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_holders + token.token_address)
        assert response.status_code == 404

    # ＜エラー系4_11＞
    # ＜発行体相違＞
    #   トークン名称取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_11(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_token_name + token.token_address)
        assert response.status_code == 404

    # ＜エラー系4_12＞
    # ＜発行体相違＞
    #   保有者詳細: 異なる発行体管理化のトークンアドレス
    def test_error_4_12(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_13＞
    # ＜発行体相違＞
    #   有効化: 異なる発行体管理化のトークンアドレス
    def test_error_4_13(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_14＞
    # ＜発行体相違＞
    #   無効化: 異なる発行体管理化のトークンアドレス
    def test_error_4_14(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
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

    # ＜エラー系4_15＞
    # ＜発行体相違＞
    #   募集申込開始: 異なる発行体管理化のトークンアドレス
    def test_error_4_15(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_start_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系4_16＞
    # ＜発行体相違＞
    #   募集申込停止: 異なる発行体管理化のトークンアドレス
    def test_error_4_16(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_stop_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系4_17＞
    # ＜発行体相違＞
    #   保有者リスト履歴: 異なる発行体管理化のトークンアドレス
    def test_error_4_17(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')
        account_address = eth_account['trader']['account_address']

        response = client.get(self.url_holder + token.token_address + '/' + account_address)
        assert response.status_code == 404

        response = client.post(
            self.url_allot + token.token_address + '/' + account_address,
            data={
                'amount': 1
            }
        )
        assert response.status_code == 404

    # ＜エラー系4_18＞
    # ＜発行体相違＞
    #   保有者リストCSVダウンロード: 異なる発行体管理化のトークンアドレス
    def test_error_4_18(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.post(
            self.url_holders_csv_history,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 404

    # ＜エラー系4_19＞
    # ＜発行体相違＞
    #   保有者リスト履歴（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_19(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_SHARE,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_holders_csv_history + '/' + token.token_address)
        assert response.status_code == 404

    #############################################################################
    # 後処理
    #############################################################################
    def test_end(self, db):
        clean_issue_event(db)
