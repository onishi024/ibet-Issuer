# -*- coding:utf-8 -*-
import json
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from config import Config
from app.models import Token
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, clean_issue_event
from .utils.contract_utils_payment_gateway import register_payment_account
from .utils.contract_utils_personal_info import register_personal_info


class TestAPI(TestBase):
    # テスト対象URL
    url_bond_holders = 'api/bond/holders/'  # 保有者一覧(債券)

    # PersonalInfo情報の暗号化
    personal_info_json = {
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
    encrypted_info = base64.encodebytes(cipher.encrypt(json.dumps(personal_info_json).encode('utf-8')))

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
            self.encrypted_info
        )

        # 銀行口座情報登録
        register_payment_account(
            eth_account['issuer'],
            shared_contract['PaymentGateway'],
            self.encrypted_info
        )

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
                    'returnAmount': '商品券をプレゼント',
                    'purpose': '新商品の開発資金として利用。',
                    'tradableExchange': shared_contract['IbetStraightBondExchange']['address'],
                    'personalInfoAddress': shared_contract['PersonalInfo']['address'],
                    'memo': 'メモ'
                }
            )
            # DB登録処理
            processor_issue_event(db)

    #############################################################################
    # 正常系
    #############################################################################

    # ＜正常系1＞
    #   債券保有者一覧(API)
    def test_normal_1(self, app):
        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        client, jwt = self.client_with_api_login(app)

        # 保有者一覧の参照
        response = client.get(
            self.url_bond_holders + token.token_address,
            headers={'Authorization': 'JWT ' + jwt}
        )
        assert response.status_code == 200
        assert json.loads(response.data.decode('utf-8')) == [{
            'account_address': '0x2e98E5e4098d838900509703FA8ee220E31eEdEE',
            'name': '株式会社１',
            'postal_code': '1234567',
            'address': '東京都中央区　日本橋11-1　東京マンション１０１',
            'address_type': 1,
            'email': 'abcd1234@aaa.bbb.cc',
            "commitment": 0,
            'balance': 1000000,
            'birth_date': '20190902'
        }]

    #############################################################################
    # エラー系
    #############################################################################

    # ＜エラー系1＞
    #   債券保有者一覧(API)
    def test_error_1(self, app):
        # 発行済みトークン情報を取得
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        client, _ = self.client_with_api_login(app)

        # 保有者一覧の参照（JWTなし）
        response = client.get(
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
