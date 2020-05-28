# -*- coding:utf-8 -*-
import base64
import json
from datetime import datetime

import pytest
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from app.models import Token, HolderList, Issuer
from config import Config
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, clean_issue_event, index_transfer_event
from .utils.contract_utils_payment_gateway import register_payment_account
from .utils.contract_utils_personal_info import register_personal_info

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
key = RSA.importKey(open('data/rsa/public.pem').read())
cipher = PKCS1_OAEP.new(key)
issuer_encrypted_info = base64.encodebytes(cipher.encrypt(json.dumps(issuer_personal_info_json).encode('utf-8')))

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
trader_encrypted_info = base64.encodebytes(cipher.encrypt(json.dumps(trader_personal_info_json).encode('utf-8')))


@pytest.fixture(scope="class", autouse=True)
def setup(db, shared_contract):
    Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
    Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
    Config.AGENT_ADDRESS = eth_account['agent']['account_address']
    Config.IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetShareExchange']['address']
    Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetStraightBondExchange']['address']
    Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetMembershipExchange']['address']
    Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS = shared_contract['PaymentGateway']['address']
    Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
    Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

    # PersonalInfo登録
    register_personal_info(
        eth_account['issuer'],
        shared_contract['PersonalInfo'],
        issuer_encrypted_info
    )
    register_personal_info(
        eth_account['trader'],
        shared_contract['PersonalInfo'],
        trader_encrypted_info
    )

    # 銀行口座情報登録
    register_payment_account(
        eth_account['issuer'],
        shared_contract['PaymentGateway'],
        issuer_encrypted_info
    )

    # 発行体名義登録
    issuer = Issuer()
    issuer.eth_account = eth_account['issuer']['account_address']
    issuer.issuer_name = '発行体１'
    db.session.add(issuer)


class TestAPIShareHolders(TestBase):
    # テスト対象URL
    url_share_holders = 'api/share/holders/'  # 保有者一覧(株式)

    #############################################################################
    # 前処理
    #############################################################################
    def test_start(self, app, db, shared_contract):
        # 株式新規発行
        with self.client_with_admin_login(app) as client:
            # 新規発行
            r = client.post(
                '/share/issue',
                data={
                    'name': 'テスト株',
                    'symbol': 'SHARE',
                    'totalSupply': 1000000,
                    'issuePrice': 1000,
                    'dividends': 100.25,
                    'dividendRecordDate': '20200401',
                    'dividendPaymentDate': '20200501',
                    'cancellationDate': '20200601',
                    'transferable': 'True',
                    'memo': 'メモ1234',
                    'referenceUrls_1': 'http://example.com',
                    'referenceUrls_2': 'http://image.png',
                    'referenceUrls_3': 'http://image3.org/abc',
                    'contact_information': '問い合わせ先ABCDEFG',
                    'privacy_policy': 'プライバシーポリシーXYZ',
                    'tradableExchange': shared_contract['IbetShareExchange']['address'],
                    'personalInfoAddress': shared_contract['PersonalInfo']['address'],
                }
            )

            # DB登録処理
            processor_issue_event(db)

            token = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SHARE).first()

            # 保有者移転
            client.post(
                '/share/transfer_ownership/' + token.token_address + '/' + eth_account['issuer']['account_address'],
                data={
                    'to_address': eth_account['trader']['account_address'],
                    'amount': 10
                }
            )
            # DB登録処理
            # Transferイベント登録
            index_transfer_event(
                db,
                '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
                token.token_address,
                eth_account['issuer']['account_address'],
                eth_account['trader']['account_address'],
                10
            )

    #############################################################################
    # 正常系
    #############################################################################

    # ＜正常系1＞
    #   株式保有者一覧(API)
    def test_normal_1(self, app):
        # DB登録データの検証用にテスト開始時刻を取得
        test_started = datetime.utcnow()

        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SHARE).all()
        token = tokens[0]

        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.post(
            self.url_share_holders + token.token_address,
            headers={'Authorization': 'JWT ' + jwt}
        )

        # レスポンスの検証
        assert response.status_code == 201

        # DB登録内容の検証
        # 他のテストでの更新されている可能性を考慮し、複数件取得する
        rows = HolderList.query.filter(HolderList.token_address == token.token_address) \
            .filter(HolderList.created >= test_started) \
            .all()

        csv_data = '\n'.join([
            # CSVヘッダ
            ",".join([
                'token_name', 'token_address', 'account_address',
                'balance', 'commitment',
                'name', 'birth_date', 'postal_code', 'address', 'email'
            ]),
            # CSVデータ
            ','.join([
                'テスト株', token.token_address, eth_account['issuer']['account_address'],
                '999990', '0',
                '発行体１', '--', '--', '--', '--'
            ]),
            ','.join([
                'テスト株', token.token_address, eth_account['trader']['account_address'],
                '10', '0',
                'ﾀﾝﾀｲﾃｽﾄ', '20191102', '1040053', '東京都中央区　勝どき1丁目１-２ー３', 'abcd1234@aaa.bbb.cc'
            ])
        ]) + '\n'
        assumed_binary_data = csv_data.encode('sjis', 'ignore')

        # CSVデータが一致するレコードが1件のみ存在することを検証する
        assert len(list(filter(lambda row: row.holder_list == assumed_binary_data, rows))) == 1

    #############################################################################
    # エラー系
    #############################################################################

    # ＜エラー系1＞
    #   株式保有者一覧(API)
    #   入力エラー（存在しないトークン）：400
    def test_error_1(self, app):
        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.post(
            self.url_share_holders + '0x0000000000000000000000000000000000000111',  # 存在しないトークンアドレス
            headers={'Authorization': 'JWT ' + jwt}
        )
        assert response.status_code == 404
        assert json.loads(response.data.decode('utf-8')) == {
            'error': 'Not Found',
            'status_code': 404
        }

    # ＜エラー系2＞
    #   株式保有者一覧(API)
    #   認証エラー：401
    def test_error_2(self, app):
        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SHARE).all()
        token = tokens[0]

        client, _ = self.client_with_api_login(app)

        # 保有者一覧の参照（JWTなし）
        response = client.post(
            self.url_share_holders + token.token_address,
            headers={}
        )
        assert response.status_code == 401
        assert json.loads(response.data.decode('utf-8')) == {
            'description': 'Request does not contain an access token',
            'error': 'Authorization Required',
            'status_code': 401
        }


class TestAPIBondHolders(TestBase):
    # テスト対象URL
    url_bond_holders = 'api/bond/holders/'  # 保有者一覧(債券)

    #############################################################################
    # 前処理
    #############################################################################
    def test_start(self, app, db, shared_contract):
        # 債券新規発行
        with self.client_with_admin_login(app) as client:
            # 新規発行
            client.post(
                '/bond/issue',
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
            # DB登録処理
            processor_issue_event(db)

            token = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).first()

            # 保有者移転
            client.post(
                '/bond/transfer_ownership/' + token.token_address + '/' + eth_account['issuer']['account_address'],
                data={
                    'to_address': eth_account['trader']['account_address'],
                    'amount': 10
                }
            )
            # DB登録処理
            # Transferイベント登録
            index_transfer_event(
                db,
                '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
                token.token_address,
                eth_account['issuer']['account_address'],
                eth_account['trader']['account_address'],
                10
            )

    #############################################################################
    # 正常系
    #############################################################################

    # ＜正常系1＞
    #   債券保有者一覧(API)
    def test_normal_1(self, app):
        # DB登録データの検証用にテスト開始時刻を取得
        test_started = datetime.utcnow()

        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.post(
            self.url_bond_holders + token.token_address,
            headers={'Authorization': 'JWT ' + jwt}
        )

        # レスポンスの検証
        assert response.status_code == 201

        # DB登録内容の検証
        # 他のテストでの更新されている可能性を考慮し、複数件取得する
        rows = HolderList.query.filter(HolderList.token_address == token.token_address) \
            .filter(HolderList.created >= test_started) \
            .all()

        csv_data = '\n'.join([
            # CSVヘッダ
            ",".join([
                'token_name', 'token_address', 'account_address',
                'balance', 'commitment', 'total_balance', 'total_holdings',
                'name', 'birth_date', 'postal_code', 'address', 'email'
            ]),
            # CSVデータ
            ','.join([
                'テスト債券', token.token_address, eth_account['issuer']['account_address'],
                '999990', '0', '999990', '999990000',
                '発行体１', '--', '--', '--', '--'
            ]),
            ','.join([
                'テスト債券', token.token_address, eth_account['trader']['account_address'],
                '10', '0', '10', '10000',
                'ﾀﾝﾀｲﾃｽﾄ', '20191102', '1040053', '東京都中央区　勝どき1丁目１-２ー３', 'abcd1234@aaa.bbb.cc'
            ])
        ]) + '\n'
        assumed_binary_data = csv_data.encode('sjis', 'ignore')

        # CSVデータが一致するレコードが1件のみ存在することを検証する
        assert len(list(filter(lambda row: row.holder_list == assumed_binary_data, rows))) == 1

    #############################################################################
    # エラー系
    #############################################################################

    # ＜エラー系1＞
    #   債券保有者一覧(API)
    #   入力エラー（存在しないトークン）：400
    def test_error_1(self, app):
        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.post(
            self.url_bond_holders + '0x0000000000000000000000000000000000000111',  # 存在しないトークンアドレス
            headers={'Authorization': 'JWT ' + jwt}
        )
        assert response.status_code == 404
        assert json.loads(response.data.decode('utf-8')) == {
            'error': 'Not Found',
            'status_code': 404
        }

    # ＜エラー系2＞
    #   債券保有者一覧(API)
    #   認証エラー：401
    def test_error_2(self, app):
        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        client, _ = self.client_with_api_login(app)

        # 保有者一覧の参照（JWTなし）
        response = client.post(
            self.url_bond_holders + token.token_address,
            headers={}
        )
        assert response.status_code == 401
        assert json.loads(response.data.decode('utf-8')) == {
            'description': 'Request does not contain an access token',
            'error': 'Authorization Required',
            'status_code': 401
        }


class TestAPIMembershipHolders(TestBase):
    # テスト対象URL
    url_membership_holders = 'api/membership/holders/'  # 保有者一覧(会員権)

    #############################################################################
    # 前処理
    #############################################################################
    def test_start(self, app, db, shared_contract):
        # 会員権新規発行
        with self.client_with_admin_login(app) as client:
            # 新規発行
            client.post(
                '/membership/issue',
                data={
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
                    'tradableExchange': shared_contract['IbetMembershipExchange']['address'],
                }
            )
            # DB登録処理
            processor_issue_event(db)

            token = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).first()

            # 保有者移転
            client.post(
                '/membership/transfer_ownership/' + token.token_address + '/' + eth_account['issuer'][
                    'account_address'],
                data={
                    'to_address': eth_account['trader']['account_address'],
                    'amount': 10
                }
            )
            # DB登録処理
            # Transferイベント登録
            index_transfer_event(
                db,
                '0xac22f75bae96f8e9f840f980dfefc1d497979341d3106aeb25e014483c3f414a',  # 仮のトランザクションハッシュ
                token.token_address,
                eth_account['issuer']['account_address'],
                eth_account['trader']['account_address'],
                10
            )

    #############################################################################
    # 正常系
    #############################################################################

    # ＜正常系1＞
    #   会員権保有者一覧(API)
    def test_normal_1(self, app):
        # DB登録データの検証用にテスト開始時刻を取得
        test_started = datetime.utcnow()

        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]

        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.post(
            self.url_membership_holders + token.token_address,
            headers={'Authorization': 'JWT ' + jwt}
        )

        # レスポンスの検証
        assert response.status_code == 201

        # DB登録内容の検証
        # 他のテストでの更新されている可能性を考慮し、複数件取得する
        rows = HolderList.query.filter(HolderList.token_address == token.token_address) \
            .filter(HolderList.created >= test_started) \
            .all()

        csv_data = '\n'.join([
            # CSVヘッダ
            ",".join([
                'token_name', 'token_address', 'account_address',
                'balance', 'commitment',
                'name', 'birth_date', 'postal_code', 'address', 'email'
            ]),
            # CSVデータ
            ','.join([
                'テスト会員権', token.token_address, eth_account['issuer']['account_address'],
                '999990', '0',
                '発行体１', '--', '--', '--', '--'
            ]),
            ','.join([
                'テスト会員権', token.token_address, eth_account['trader']['account_address'],
                '10', '0',
                'ﾀﾝﾀｲﾃｽﾄ', '20191102', '1040053', '東京都中央区　勝どき1丁目１-２ー３', 'abcd1234@aaa.bbb.cc'
            ])
        ]) + '\n'
        assumed_binary_data = csv_data.encode('sjis', 'ignore')

        # CSVデータが一致するレコードが1件のみ存在することを検証する
        assert len(list(filter(lambda row: row.holder_list == assumed_binary_data, rows))) == 1

    #############################################################################
    # エラー系
    #############################################################################

    # ＜エラー系1＞
    #   会員権保有者一覧(API)
    #   入力エラー（存在しないトークン）：400
    def test_error_1(self, app):
        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.post(
            self.url_membership_holders + '0x0000000000000000000000000000000000000111',  # 存在しないトークンアドレス
            headers={'Authorization': 'JWT ' + jwt}
        )
        assert response.status_code == 404
        assert json.loads(response.data.decode('utf-8')) == {
            'error': 'Not Found',
            'status_code': 404
        }

    # ＜エラー系2＞
    #   会員権保有者一覧(API)
    #   認証エラー：401
    def test_error_2(self, app):
        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()
        token = tokens[0]

        client, _ = self.client_with_api_login(app)

        # 保有者一覧の参照（JWTなし）
        response = client.post(
            self.url_membership_holders + token.token_address,
            headers={}
        )
        assert response.status_code == 401
        assert json.loads(response.data.decode('utf-8')) == {
            'description': 'Request does not contain an access token',
            'error': 'Authorization Required',
            'status_code': 401
        }


#############################################################################
# 後処理
#############################################################################
@pytest.fixture(scope='class', autouse=True)
def test_end(db):
    yield

    clean_issue_event(db)

    Issuer.query.filter(Issuer.eth_account == Config.ETH_ACCOUNT).delete()
