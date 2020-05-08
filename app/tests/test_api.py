# -*- coding:utf-8 -*-
import base64
import json
from datetime import datetime

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from app.models import Token, HolderList, Issuer
from config import Config
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, clean_issue_event, index_transfer_event
from .utils.contract_utils_payment_gateway import register_payment_account
from .utils.contract_utils_personal_info import register_personal_info


class TestAPI(TestBase):
    # テスト対象URL
    url_bond_holders = 'api/bond/holders/'  # 保有者一覧(債券)

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

    #############################################################################
    # 前処理
    #############################################################################
    def test_start(self, app, db, shared_contract):
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetStraightBondExchange']['address']
        Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS = shared_contract['PaymentGateway']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        # PersonalInfo登録
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

        # 銀行口座情報登録
        register_payment_account(
            eth_account['issuer'],
            shared_contract['PaymentGateway'],
            self.issuer_encrypted_info
        )

        # 発行体名義登録
        issuer = Issuer()
        issuer.eth_account = eth_account['issuer']['account_address']
        issuer.issuer_name = '発行体１'
        db.session.add(issuer)

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

            token = Token.query.first()

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

        assert rows[0].holder_list.decode('sjis') == csv_data
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
        assert response.status_code == 400
        assert json.loads(response.data.decode('utf-8')) == {
            'description': 'Invalid token_address',
            'error': 'Bad Request',
            'status_code': 400
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

    #############################################################################
    # 後処理
    #############################################################################
    def test_end(self, db):
        clean_issue_event(db)

        Issuer.query.filter(Issuer.eth_account == Config.ETH_ACCOUNT).delete()
