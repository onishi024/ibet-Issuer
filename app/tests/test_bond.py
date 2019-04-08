# -*- coding:utf-8 -*-
import time
from .conftest import TestBase
from .contract_modules import *
from .. import db
from ..models import Token
from logging import getLogger
logger = getLogger('api')

class TestBond(TestBase):

    ##################
    # URL
    ##################
    url_list = '/bond/list' # 発行済一覧
    url_positions = '/bond/positions' # 売出管理
    url_issue = '/bond/issue' # 新規発行
    url_setting = '/bond/setting/' # 詳細設定
    url_sell = 'bond/sell/' # 新規売出
    url_cancel_order = 'bond/cancel_order/' # 売出停止
    url_release = 'bond/release' # 公開
    url_holders = 'bond/holders/' # 保有者一覧
    url_holder = 'bond/holder/' # 保有者詳細
    url_signature = 'bond/request_signature/' # 認定依頼
    url_redeem = 'bond/redeem' # 償還
    url_transfer_ownership = 'bond/transfer_ownership/' # 所有者移転

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
        "email":"abcd1234@aaa.bbb.cc"
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
        "email":"abcd1234@aaa.bbb.cc"
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
        Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS = shared_contract['PaymentGateway']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        # PersonalInfo登録
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

        # PaymentGateway：収納代行利用規約登録
        register_terms(
            eth_account['agent'],
            shared_contract['PaymentGateway']
        )

        # PaymentGateway：銀行口座情報登録
        register_payment_account(
            eth_account['issuer'],
            shared_contract['PaymentGateway'],
            self.issuer_encrypted_info
        )

    # ＜正常系1＞
    #   債券一覧の参照(0件)
    def test_normal_1(self, app, shared_contract):
        # 債券一覧
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>債券一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2＞
    #   債券売出管理(0件)
    def test_normal_2(self, app, shared_contract):
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
                'redemptionAmount': 10000,
                'returnDate': '20191231',
                'returnAmount': '商品券をプレゼント',
                'purpose': '新商品の開発資金として利用。',
                'tradableExchange': shared_contract['IbetStraightBondExchange']['address'],
                'memo': 'メモ'
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # DB登録処理
        processorIssueEvent(db)

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
        assert 'メモ'.encode('utf-8') in response.data

    # ＜正常系4＞
    #   債券一覧の参照(1件)
    def test_normal_4(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data

    # ＜正常系5＞
    #   売出管理画面の参照(1件)
    def test_normal_5(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>債券売出管理'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data

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

    # ＜正常系7＞
    #   売出 → 債券売出管理で確認
    def test_normal_7(self, app, shared_contract):
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
        assert 'BOND'.encode('utf-8') in response.data
        assert '売出停止'.encode('utf-8') in response.data

    # ＜正常系8＞
    #   売出停止 → 債券売出管理で確認
    def test_normal_8(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        # 売出停止
        response = client.post(
            self.url_cancel_order + token.token_address,
        )
        assert response.status_code == 302

        # 債券売出管理を参照
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>債券売出管理'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '売出開始'.encode('utf-8') in response.data

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
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': shared_contract['PaymentGateway']['address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

        # 詳細設定画面を参照
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'https://test.com/image_1.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_3.jpg'.encode('utf-8') in response.data
        assert shared_contract['PaymentGateway']['address'].encode('utf-8') in response.data

        # データ戻し
        response = client.post(
            url_setting,
            data={
                'image_1': 'https://test.com/image_1.jpg',
                'image_2': 'https://test.com/image_2.jpg',
                'image_3': 'https://test.com/image_3.jpg',
                'tradableExchange': shared_contract['IbetStraightBondExchange']['address']
            }
        )
        assert response.status_code == 302
        time.sleep(10)

    # ＜正常系10＞
    #   公開 →　詳細設定画面で確認
    def test_normal_10(self, app, shared_contract):
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
        time.sleep(10)

        # 債券詳細設定
        url_setting = self.url_setting + token.token_address
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '公開中です。公開開始までに数分程かかることがあります。'.encode('utf-8') in response.data

    # ＜正常系11＞
    #   債券保有者一覧
    def test_normal_11(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]
        client = self.client_with_admin_login(app)

        # 保有者一覧の参照
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>債券保有者一覧'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '1000000'.encode('utf-8') in response.data

    # ＜正常系12＞
    #   債券保有者詳細
    def test_normal_12(self, app, shared_contract):
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
    def test_normal_13(self, app, shared_contract):
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
        time.sleep(10)

        # 債券詳細設定画面を参照
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '認定依頼を受け付けました。'.encode('utf-8') in response.data

    # ＜正常系14＞
    #   認定実施　→　債券詳細で確認
    def test_normal_14(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
        token = tokens[0]

        # 認定処理
        exec_sign(token.token_address, eth_account['agent'])

        # 債券一覧
        url_setting = self.url_setting + token.token_address
        client = self.client_with_admin_login(app)
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert '認定済みアドレス'.encode('utf-8') in response.data
        assert eth_account['agent']['account_address'].encode('utf-8') in response.data

    # ＜正常系15＞
    #   償還実施　→　債券一覧で確認
    def test_normal_15(self, app, shared_contract):
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
        time.sleep(10)

        # 債券一覧を参照
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '償還済'.encode('utf-8') in response.data

    # ＜正常系16_1＞
    # ＜所有者移転＞
    #   所有者移転画面の参照
    def test_normal_16_1(self, app):
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

    # ＜正常系16_2＞
    # ＜所有者移転＞
    #   所有者移転処理　→　保有者一覧の参照
    def test_normal_16_2(self, app):
        client = self.client_with_admin_login(app)
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()
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
        assert '<title>債券保有者一覧'.encode('utf-8') in response.data

        # 発行体
        assert issuer_address.encode('utf-8') in response.data
        assert '<td>株式会社１</td>\n            <td>999990</td>\n            <td>0</td>'.\
            encode('utf-8') in response.data

        # 投資家
        assert trader_address.encode('utf-8') in response.data
        assert '<td>ﾀﾝﾀｲﾃｽﾄ</td>\n            <td>10</td>\n            <td>0</td>'.\
            encode('utf-8') in response.data


    #############################################################################
    # エラー系
    #############################################################################
    # ＜エラー系1＞
    #   債券新規発行（必須エラー）
    def test_error_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>債券新規発行'.encode('utf-8') in response.data
        assert '商品名は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data
        assert '発行目的は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系1＞
    #   債券新規発行（DEXアドレスのフォーマットエラー）
    def test_error_1_2(self, app, shared_contract):
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
                'redemptionAmount': 10000,
                'returnDate': '20191231',
                'returnAmount': '商品券をプレゼント',
                'purpose': '新商品の開発資金として利用。',
                'tradableExchange': error_address,
                'memo': 'メモ'
            }
        )
        assert response.status_code == 200
        assert '<title>債券新規発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data

    # ＜エラー系1＞
    #   設定画面（DEXアドレスのフォーマットエラー）
    def test_error_1_3(self, app, shared_contract):
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
    def test_error_2(self, app, shared_contract):
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
    def test_error_3(self, app, shared_contract):
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
    def test_error_4(self, app, shared_contract):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)
        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
                'signer': '0xc94b0d702422587e361dd6cd08b55dfe1961181f1' # 1桁多い
            }
        )
        assert response.status_code == 200
        assert '有効なアドレスではありません。'.encode('utf-8') in response.data


    # ＜エラー系5＞
    #   認定（認定依頼がすでに登録されている）
    def test_error_5(self, app, shared_contract):
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
            self.url_transfer_ownership + error_address + '/' + issuer_address ,
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
            self.url_transfer_ownership + token.token_address + '/' + error_address ,
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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
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
            self.url_transfer_ownership + token.token_address + '/' + issuer_address ,
            data={
                'to_address': trader_address,
                'amount': 1000001
            }
        )
        assert response.status_code == 200
        assert '移転数量が残高を超えています。'.encode('utf-8') in response.data
