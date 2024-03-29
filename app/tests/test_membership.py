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
from datetime import (
    datetime,
    timezone
)
import json
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

import pytest
from eth_utils import to_checksum_address

from config import Config
from app.models import (
    Token,
    HolderList,
    Transfer
)
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import (
    processor_issue_event,
    index_transfer_event,
    clean_issue_event
)
from .utils.contract_utils_membership import (
    get_latest_orderid,
    get_latest_agreementid,
    take_buy,
    confirm_agreement,
    apply_for_offering
)
from .utils.contract_utils_personal_info import register_personal_info


class TestMembership(TestBase):

    #############################################################################
    # テスト対象URL
    #############################################################################
    url_list = 'membership/list'  # 発行済一覧
    url_positions = 'membership/positions'  # 売出管理
    url_issue = 'membership/issue'  # 新規発行
    url_setting = 'membership/setting/'  # 詳細設定
    url_sell = 'membership/sell/'  # 新規売出
    url_cancel_order = 'membership/cancel_order/'  # 売出中止
    url_release = 'membership/release'  # 公開
    url_invalid = 'membership/invalid'  # 無効化（取扱中止）
    url_valid = 'membership/valid'  # 有効化（取扱開始）
    url_start_initial_offering = 'membership/start_initial_offering'  # 募集申込開始
    url_stop_initial_offering = 'membership/stop_initial_offering'  # 募集申込停止
    url_applications = 'membership/applications/'  # 募集申込一覧
    url_get_applications = 'membership/get_applications/'  # 募集申込一覧
    url_applications_csv_download = 'membership/applications_csv_download'  # 申込者リストCSVダウンロード
    url_allocate = 'membership/allocate'  # 割当（募集申込）
    url_add_supply = 'membership/add_supply/'  # 追加発行
    url_holders = 'membership/holders/'  # 保有者一覧
    url_get_holders = 'membership/get_holders/'  # 保有者一覧（API）
    url_holders_csv_download = 'membership/holders_csv_download'  # 保有者一覧CSVダウンロード
    url_get_token_name = 'membership/get_token_name/'  # トークン名取得（API）
    url_holder = 'membership/holder/'  # 保有者詳細
    url_transfer_ownership = 'membership/transfer_ownership/'  # 所有者移転
    url_holders_csv_history = 'membership/holders_csv_history/'  # 保有者リスト履歴
    url_get_holders_csv_history = 'membership/get_holders_csv_history/'  # 保有者リスト履歴（API）
    url_holders_csv_history_download = 'membership/holders_csv_history_download'  # 保有者リストCSVダウンロード
    url_token_tracker = 'membership/token/track/'  # トークン追跡

    #############################################################################
    # テスト用会員権トークン情報
    #############################################################################
    # Token_1：最初に新規発行されるトークン。
    token_data1 = {
        'name': 'テスト会員権',
        'symbol': 'KAIINKEN',
        'totalSupply': 1000000,
        'details': 'details',
        'return_details': 'returnDetails',
        'expirationDate': '20191231',
        'memo': 'memo',
        'transferable': 'True',
        'image_1': 'http://hoge.co.jp',
        'image_2': 'http://hoge.co.jp',
        'image_3': 'http://hoge.co.jp',
    }
    # Token_2：2番目に発行されるトークン。imageなし, transferable:False
    token_data2 = {
        'name': '2件目会員権',
        'symbol': '2KENME',
        'totalSupply': 2000000,
        'details': '2details',
        'return_details': '2returnDetails',
        'expirationDate': '20201231',
        'memo': '2memo',
        'transferable': 'False',
        'image_1': '',
        'image_2': '',
        'image_3': ''
    }
    # Token_3：設定変更用情報
    token_data3 = {
        'name': 'テスト会員権',
        'symbol': 'KAIINKEN',
        'totalSupply': 1000000,
        'details': '3details',
        'return_details': '3returnDetails',
        'expirationDate': '20211231',
        'memo': '3memo',
        'transferable': 'False',
        'image_1': 'http://hoge.co.jp',
        'image_2': 'http://hoge.co.jp',
        'image_3': 'http://hoge.co.jp'
    }

    @staticmethod
    def get_token(num):
        tokens = Token.query. \
            filter_by(
                template_id=Config.TEMPLATE_ID_MEMBERSHIP,
                admin_address=eth_account['issuer']['account_address'].lower()
            ). \
            order_by(Token.created). \
            all()
        return tokens[num]

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
        "key_manager": "",
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
    # テスト（正常系）
    #############################################################################

    # ＜前処理＞
    def test_normal_0(self, shared_contract, db):
        self.token_data1['tradableExchange'] = \
            shared_contract['IbetMembershipExchange']['address']
        self.token_data2['tradableExchange'] = \
            shared_contract['IbetMembershipExchange']['address']
        self.token_data3['tradableExchange'] = \
            shared_contract['PersonalInfo']['address']

    # ＜正常系1_1＞
    # ＜会員権の0件確認＞
    #   発行済一覧画面の参照(0件)
    def test_normal_1_1(self, app):
        # 発行済一覧の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>発行済一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # ＜会員権の0件確認＞
    #   売出管理画面の参照(0件)
    def test_normal_1_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2_1＞
    # ＜会員権の1件確認＞
    #   新規発行　→　詳細設定画面の参照
    def test_normal_2_1(self, app, db):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data=self.token_data1
        )
        assert response.status_code == 302

        # DB登録処理
        processor_issue_event(db)

        # 詳細設定画面の参照
        token = TestMembership.get_token(0)
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply']).encode('utf-8') in response.data
        assert self.token_data1['details'].encode('utf-8') in response.data
        assert self.token_data1['return_details'].encode('utf-8') in response.data
        assert self.token_data1['expirationDate'].encode('utf-8') in response.data
        assert self.token_data1['memo'].encode('utf-8') in response.data
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data
        assert self.token_data1['image_1'].encode('utf-8') in response.data
        assert self.token_data1['image_2'].encode('utf-8') in response.data
        assert self.token_data1['image_3'].encode('utf-8') in response.data
        assert self.token_data1['tradableExchange'].encode('utf-8') in response.data

    # ＜正常系2_2＞
    # ＜会員権の1件確認＞
    #   発行済一覧画面の参照(1件)
    def test_normal_2_2(self, app):
        token = TestMembership.get_token(0)

        # 発行済一覧画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>発行済一覧'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '取扱中'.encode('utf-8') in response.data

    # ＜正常系2_3＞
    # ＜会員権の1件確認＞
    #   売出管理画面の参照(1件)
    def test_normal_2_3(self, app):
        token = TestMembership.get_token(0)

        # 売出管理画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data
        assert '<td>1,000,000</td>\n                    <td>1,000,000</td>\n                    <td>0</td>'.\
                   encode('utf-8') in response.data

    # ＜正常系3_1＞
    # ＜発行済一覧（複数件）＞
    #   新規発行（画像URLなし）　→　詳細設定画面の参照
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
        token = TestMembership.get_token(1)
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert self.token_data2['symbol'].encode('utf-8') in response.data
        assert str(self.token_data2['totalSupply']).encode('utf-8') in response.data
        assert self.token_data2['details'].encode('utf-8') in response.data
        assert self.token_data2['return_details'].encode('utf-8') in response.data
        assert self.token_data2['expirationDate'].encode('utf-8') in response.data
        assert self.token_data2['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data2['image_1'].encode('utf-8') in response.data
        assert self.token_data2['image_2'].encode('utf-8') in response.data
        assert self.token_data2['image_3'].encode('utf-8') in response.data

    # ＜正常系3_2＞
    # ＜発行済一覧（複数件）＞
    #   発行済一覧画面の参照（複数件）
    def test_normal_3_2(self, app):
        token1 = TestMembership.get_token(0)
        token2 = TestMembership.get_token(1)

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

    # ＜正常系3_3＞
    # ＜発行済一覧（複数件）＞
    #   売出管理画面の参照（複数件）
    def test_normal_3_3(self, app):
        token1 = TestMembership.get_token(0)
        token2 = TestMembership.get_token(1)

        # 売出管理画面の参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data

        # Token_1
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert token1.token_address.encode('utf-8') in response.data
        assert '<td>1,000,000</td>\n                    <td>1,000,000</td>\n                    <td>0</td>'. \
                   encode('utf-8') in response.data

        # Token_2
        assert self.token_data2['name'].encode('utf-8') in response.data
        assert token2.token_address.encode('utf-8') in response.data
        assert '<td>2,000,000</td>\n                    <td>2,000,000</td>\n                    <td>0</td>'. \
                   encode('utf-8') in response.data

    # ＜正常系4_1＞
    # ＜売出画面＞
    #   新規売出画面の参照
    #   ※Token_1が対象
    def test_normal_4_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 新規売出画面の参照
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>新規売出'.encode('utf-8') in response.data
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert "{:,}".format(self.token_data1['totalSupply']).encode('utf-8') in response.data
        assert self.token_data1['details'].encode('utf-8') in response.data
        assert self.token_data1['expirationDate'].encode('utf-8') in response.data
        assert 'なし'.encode('utf-8') in response.data
        assert self.token_data1['tradableExchange'].encode('utf-8') in response.data

    # ＜正常系4_2＞
    # ＜売出画面＞
    #   売出処理 → 売出管理画面の参照
    #   ※Token_1が対象
    def test_normal_4_2(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
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
        assert self.token_data1['name'].encode('utf-8') in response.data
        # 売出中の数量が存在する
        assert '<td>1,000,000</td>\n                    <td>0</td>\n                    <td>1,000,000</td>'.\
                   encode('utf-8') in response.data

    # ＜正常系4_3＞
    # ＜売出画面＞
    #   売出停止処理 → 売出管理で確認
    #   ※Token_1が対象
    def test_normal_4_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 売出停止処理
        response = client.post(
            self.url_cancel_order + token.token_address + '/1',
        )
        assert response.status_code == 302

        # 売出管理画面の参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>売出管理'.encode('utf-8') in response.data
        assert 'テスト会員権'.encode('utf-8') in response.data
        # 売出中の数量が0
        assert '<td>1,000,000</td>\n                    <td>1,000,000</td>\n                    <td>0</td>'.\
                   encode('utf-8') in response.data

    # ＜正常系5_1＞
    # ＜詳細設定＞
    #   売出　→　詳細設定（設定変更）　→　詳細設定画面参照
    #   ※Token_1が対象、Token_3の状態に変更
    def test_normal_5_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 売出処理
        url_sell = self.url_sell + token.token_address
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302

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
        assert self.token_data3['name'].encode('utf-8') in response.data
        assert self.token_data3['symbol'].encode('utf-8') in response.data
        assert str(self.token_data3['totalSupply']).encode('utf-8') in response.data
        assert self.token_data3['details'].encode('utf-8') in response.data
        assert self.token_data3['return_details'].encode('utf-8') in response.data
        assert self.token_data3['expirationDate'].encode('utf-8') in response.data
        assert self.token_data3['memo'].encode('utf-8') in response.data
        assert '<option selected value="False">あり</option>'.encode('utf-8') in response.data
        assert self.token_data3['image_1'].encode('utf-8') in response.data
        assert self.token_data3['image_2'].encode('utf-8') in response.data
        assert self.token_data3['image_3'].encode('utf-8') in response.data
        assert self.token_data3['tradableExchange'].encode('utf-8') in response.data

        # データ戻し
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data=self.token_data1
        )
        assert response.status_code == 302

    # ＜正常系5_2＞
    # ＜詳細設定＞
    #   同じ値で更新処理　→　各値に変更がないこと
    def test_normal_5_2(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
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
        assert self.token_data1['name'].encode('utf-8') in response.data
        assert self.token_data1['symbol'].encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply']).encode('utf-8') in response.data
        assert self.token_data1['details'].encode('utf-8') in response.data
        assert self.token_data1['return_details'].encode('utf-8') in response.data
        assert self.token_data1['expirationDate'].encode('utf-8') in response.data
        assert self.token_data1['memo'].encode('utf-8') in response.data
        assert '<option selected value="True">なし</option>'.encode('utf-8') in response.data
        assert self.token_data1['image_1'].encode('utf-8') in response.data
        assert self.token_data1['image_2'].encode('utf-8') in response.data
        assert self.token_data1['image_3'].encode('utf-8') in response.data
        assert self.token_data1['tradableExchange'].encode('utf-8') in response.data
        # 公開済でないことを確認
        assert '公開 <i class="fa fa-exclamation-triangle">'.encode('utf-8') in response.data

    # ＜正常系5_3＞
    # ＜設定画面＞
    #   公開処理　→　公開済状態になること
    #   ※Token_1が対象
    def test_normal_5_3(self, app):
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

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert '公開済'.encode('utf-8') in response.data

    # ＜正常系5_4＞
    # ＜設定画面＞
    #   取扱停止処理　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_4(self, app):
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

    # ＜正常系5_5＞
    # ＜設定画面＞
    #   取扱開始　→　一覧画面、詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_5(self, app):
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

    # ＜正常系5_6＞
    # ＜設定画面＞
    #   追加発行画面参照　→　追加発行処理　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_5_6(self, app):
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

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert str(self.token_data1['totalSupply'] + 10).encode('utf-8') in response.data

    # ＜正常系6_1＞
    # ＜保有者一覧＞
    #   保有者一覧で確認(1件)
    #   ※Token_1が対象
    def test_normal_6_1(self, app, shared_contract, db):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 発行体のpersonalInfo登録
        register_personal_info(
            db=db,
            invoker=eth_account["issuer"],
            contract_address=shared_contract["PersonalInfo"]["address"],
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
        assert eth_account['issuer']['account_address'] == response_data[0]['account_address']
        assert '発行体１' == response_data[0]['name']
        assert '--' == response_data[0]['postal_code']
        assert '--' == response_data[0]['address']
        assert '--' == response_data[0]['email']
        assert '--' == response_data[0]['birth_date']
        assert 10 == response_data[0]['balance']
        assert 1000000 == response_data[0]['commitment']

        # トークン名APIの参照
        response = client.get(self.url_get_token_name + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200
        assert 'テスト会員権' == response_data

    # ＜正常系6_2＞
    # ＜保有者一覧＞
    #   約定　→　保有者一覧で確認（複数件）
    #   ※Token_1が対象
    def test_normal_6_2(self, app, shared_contract, db):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 投資家のpersonalInfo登録
        register_personal_info(
            db=db,
            invoker=eth_account["trader"],
            contract_address=shared_contract["PersonalInfo"]["address"],
            info=self.trader_personal_info_json,
            encrypted_info=self.trader_encrypted_info
        )

        # 約定データの作成
        amount = 20
        exchange = shared_contract['IbetMembershipExchange']
        orderid = get_latest_orderid(exchange)
        take_buy(eth_account['trader'], exchange, orderid, amount)
        agreementid = get_latest_agreementid(exchange, orderid)
        confirm_agreement(eth_account['agent'], exchange, orderid, agreementid)

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data_list = json.loads(response.data)

        for response_data in response_data_list:
            if eth_account['issuer']['account_address'] == response_data['account_address']:  # issuer
                assert '発行体１' == response_data['name']
                assert '--' == response_data['postal_code']
                assert '--' == response_data['address']
                assert '--' == response_data['email']
                assert '--' == response_data['birth_date']
                assert 10 == response_data['balance']
                assert 999980 == response_data['commitment']
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
        assert 'テスト会員権' == response_data

    # ＜正常系6_3＞
    # ＜保有者一覧＞
    #   保有者詳細
    #   ※Token_1が対象
    def test_normal_6_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

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
        assert '<title>所有者移転'.encode('utf-8') in response.data
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
        assert '<title>保有者一覧'.encode('utf-8') in response.data

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
                assert 0 == response_data['balance']
                assert 999980 == response_data['commitment']
            elif eth_account['trader']['account_address'] == response_data['account_address']:  # trader
                assert 'ﾀﾝﾀｲﾃｽﾄ' == response_data['name']
                assert '1040053' == response_data['postal_code']
                assert '東京都中央区　勝どき1丁目１－２−３' == response_data['address']
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
        assert 'テスト会員権' == response_data

    # ＜正常系8_1＞
    # ＜募集申込開始・停止＞
    #   初期状態：募集申込停止中（詳細設定画面で確認）
    #   ※Token_1が対象
    def test_normal_8_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 詳細設定画面の参照
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

    # ＜正常系8_2＞
    # ＜募集申込開始・停止＞
    #   募集申込開始　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_8_2(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

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
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert '募集申込停止'.encode('utf-8') in response.data

    # ＜正常系8_3＞
    # ＜募集申込開始・停止＞
    #   ※8_2の続き
    #   募集申込停止　→　詳細設定画面で確認
    #   ※Token_1が対象
    def test_normal_8_3(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

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
        assert '<title>詳細設定'.encode('utf-8') in response.data
        assert '募集申込開始'.encode('utf-8') in response.data

        # 募集申込状態に戻す
        response = client.post(
            self.url_start_initial_offering,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

    # ＜正常系9_1＞
    # ＜募集申込一覧参照＞
    #   0件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_9_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)

        # 募集申込一覧参照
        response = client.get(self.url_applications + str(token.token_address))
        assert response.status_code == 200
        assert '<title>募集申込一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系9_2＞
    # ＜募集申込一覧参照＞
    #   1件：募集申込一覧
    #   ※Token_1が対象
    def test_normal_9_2(self, db, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
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

    # ＜正常系10_1＞
    # ＜割当（募集申込）＞
    #   ※9_2の続き
    #   割当（募集申込）画面参照：GET
    #   ※Token_1が対象
    def test_normal_10_1(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        token_address = str(token.token_address)
        trader_address = eth_account['trader']['account_address']

        # 割当（募集申込）
        url = self.url_allocate + '/' + token_address + '/' + trader_address
        response = client.get(url)
        assert response.status_code == 200
        assert 'トークン割当'.encode('utf-8') in response.data
        assert token_address.encode('utf-8') in response.data
        assert trader_address.encode('utf-8') in response.data

    # ＜正常系10_2＞
    # ＜割当（募集申込）＞
    #   ※7_2, 9_2の後に実施
    #   割当（募集申込）処理　→　保有者一覧参照
    #   ※Token_1が対象
    def test_normal_10_2(self, db, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        token_address = str(token.token_address)
        issuer_address = eth_account['issuer']['account_address']
        trader_address = eth_account['trader']['account_address']

        # データ戻し：注文取消
        response = client.post(
            self.url_cancel_order + token_address + "/2",
        )
        assert response.status_code == 302

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
        assert '<title>保有者一覧'.encode('utf-8') in response.data

        # 保有者一覧APIの参照
        response = client.get(self.url_get_holders + token.token_address)
        response_data = json.loads(response.data)
        assert response.status_code == 200

        # issuer
        assert issuer_address == response_data[0]['account_address']
        assert '発行体１' == response_data[0]['name']
        assert '--' == response_data[0]['postal_code']
        assert '--' == response_data[0]['address']
        assert '--' == response_data[0]['email']
        assert '--' == response_data[0]['birth_date']
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
        assert 'テスト会員権' == response_data

    # ＜正常系11＞
    # ＜保有者一覧CSVダウンロード＞
    #   保有者一覧CSVが取得できること
    def test_normal_11(self, app):
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        token_address = str(token.token_address)

        # csvダウンロード
        url = self.url_holders_csv_download
        response = client.post(url, data={'token_address': token_address})
        assert response.status_code == 200

    # ＜正常系12-1＞
    #   保有者リスト履歴
    def test_normal_12_1(self, app):
        token = TestMembership.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        response = client.get(self.url_holders_csv_history + token.token_address)
        assert response.status_code == 200
        assert '<title>保有者リスト履歴'.encode('utf-8') in response.data
        assert token.token_address.encode('utf-8') in response.data

    # ＜正常系12-2＞
    #   保有者リスト履歴（API）
    #   0件：保有者リスト履歴
    def test_normal_12_2(self, app):
        token = TestMembership.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者一覧（API）の参照
        response = client.get(self.url_get_holders_csv_history + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert len(response_data) == 0

    # ＜正常系12-3＞
    #   保有者リスト履歴（API）
    #   1件：保有者リスト履歴
    def test_normal_12_3(self, app, db):
        token = TestMembership.get_token(0)
        client = self.client_with_admin_login(app)

        # 保有者リスト履歴を作成
        holderList = HolderList()
        holderList.token_address = token.token_address
        holderList.created = datetime(2020, 2, 29, 12, 59, 59, 1234, tzinfo=timezone.utc)
        holderList.holder_list = b'dummy csv membership test_normal_12_3'
        db.session.add(holderList)

        # 保有者一覧（API）の参照
        response = client.get(self.url_get_holders_csv_history + token.token_address)
        response_data = json.loads(response.data)

        assert response.status_code == 200
        assert len(response_data) == 1
        assert token.token_address == response_data[0]['token_address']
        assert '2020/02/29 21:59:59 +0900' == response_data[0]['created']
        assert '20200229215959membership_holders_list.csv' == response_data[0]['file_name']

    # ＜正常系12-4＞
    #   保有者リストCSVダウンロード
    #   ※12-3の続き
    def test_normal_12_4(self, app, db):
        token = TestMembership.get_token(0)

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
        assert response.data == b'dummy csv membership test_normal_12_3'

    # ＜正常系13-1＞
    #   トークン追跡
    def test_normal_13_1(self, app, db):
        token = TestMembership.get_token(0)
        client = self.client_with_admin_login(app)

        # 登録済みのトランザクションハッシュを取得
        transfer_event = Transfer.query.filter_by(token_address=token.token_address).first()
        tx_hash = transfer_event.transaction_hash

        # トークン追跡の参照
        response = client.get(self.url_token_tracker + token.token_address)

        assert response.status_code == 200
        assert '<title>トークン追跡'.encode('utf-8') in response.data
        assert tx_hash.encode('utf-8') in response.data

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
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    # ＜入力値チェック＞
    #   売出（必須エラー）
    def test_error_1_2(self, app):
        token = TestMembership.get_token(0)
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
                'return_details': '2returnDetails',
                'expirationDate': '20201231',
                'memo': '2memo',
                'transferable': 'False',
                'image_1': '',
                'image_2': '',
                'image_3': '',
                'tradableExchange': dex_address_error
            }
        )
        assert response.status_code == 200
        assert '<title>新規発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_2＞
    # ＜入力値チェック＞
    #   設定画面（DEXアドレス形式エラー）
    def test_error_2_2(self, app):
        dex_address_error = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'
        client = self.client_with_admin_login(app)
        token = TestMembership.get_token(0)
        url_setting = self.url_setting + token.token_address
        response = client.post(
            url_setting,
            data={
                'tradableExchange': dex_address_error
            }
        )
        assert response.status_code == 200
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系2_3＞
    # ＜入力値チェック＞
    #   保有者リスト履歴（アドレスのフォーマットエラー）
    def test_error_2_3(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        response = client.get(self.url_holders_csv_history + error_address)
        assert response.status_code == 404

    # ＜エラー系2_4＞
    #   保有者リスト履歴（API）（アドレスのフォーマットエラー）
    def test_error_2_4(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        response = client.get(self.url_get_holders_csv_history + error_address)
        assert response.status_code == 404

    # ＜エラー系2_5＞
    #   保有者リストCSVダウンロード（アドレスのフォーマットエラー）
    def test_error_2_5(self, app):
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

    # ＜エラー系2_6＞
    #   トークン追跡（アドレスのフォーマットエラー）
    def test_error_2_6(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        response = client.get(self.url_token_tracker + error_address)
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
        token = TestMembership.get_token(0)
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
        token = TestMembership.get_token(0)
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
        token = TestMembership.get_token(0)
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
        token = TestMembership.get_token(0)
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
        token = TestMembership.get_token(0)
        issuer_address = \
            to_checksum_address(eth_account['issuer']['account_address'])
        trader_address = \
            to_checksum_address(eth_account['trader']['account_address'])

        # 所有者移転
        response = client.post(
            self.url_transfer_ownership + token.token_address + '/' + issuer_address,
            data={
                'to_address': trader_address,
                'amount': 999971
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data

    # ＜エラー系4_1＞
    # ＜発行体相違＞
    #   トークン追跡: 異なる発行体管理化のトークンアドレス
    def test_error_4_1(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
    #   売出: 異なる発行体管理化のトークンアドレス
    def test_error_4_7(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_8＞
    # ＜発行体相違＞
    #   売出停止: 異なる発行体管理化のトークンアドレス
    def test_error_4_8(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_9＞
    # ＜発行体相違＞
    #   割当（募集申込）: 異なる発行体管理化のトークンアドレス
    def test_error_4_9(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_10＞
    # ＜発行体相違＞
    #   保有者移転: 異なる発行体管理化のトークンアドレス
    def test_error_4_10(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_11＞
    # ＜発行体相違＞
    #   保有者一覧取得（CSV）: 異なる発行体管理化のトークンアドレス
    def test_error_4_11(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_12＞
    # ＜発行体相違＞
    #   保有者一覧取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_12(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_holders + token.token_address)
        assert response.status_code == 404

    # ＜エラー系4_13＞
    # ＜発行体相違＞
    #   トークン名称取得（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_13(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
            admin_address=eth_account['issuer']['account_address'].lower()
        ).all()
        token = tokens[0]

        # 発行体2でログイン
        client = self.client_with_admin_login(app, login_id='admin2')

        response = client.get(self.url_get_token_name + token.token_address)
        assert response.status_code == 404

    # ＜エラー系4_14＞
    # ＜発行体相違＞
    #   保有者詳細: 異なる発行体管理化のトークンアドレス
    def test_error_4_14(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_15＞
    # ＜発行体相違＞
    #   有効化: 異なる発行体管理化のトークンアドレス
    def test_error_4_15(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_16＞
    # ＜発行体相違＞
    #   無効化: 異なる発行体管理化のトークンアドレス
    def test_error_4_16(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_17＞
    # ＜発行体相違＞
    #   募集申込開始: 異なる発行体管理化のトークンアドレス
    def test_error_4_17(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_18＞
    # ＜発行体相違＞
    #   募集申込停止: 異なる発行体管理化のトークンアドレス
    def test_error_4_18(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_19＞
    # ＜発行体相違＞
    #   保有者リストCSVダウンロード: 異なる発行体管理化のトークンアドレス
    def test_error_4_19(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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

    # ＜エラー系4_20＞
    # ＜発行体相違＞
    #   保有者リスト履歴（API）: 異なる発行体管理化のトークンアドレス
    def test_error_4_20(self, app):
        # 発行体1管理下のトークンアドレス
        tokens = Token.query.filter_by(
            template_id=Config.TEMPLATE_ID_MEMBERSHIP,
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
