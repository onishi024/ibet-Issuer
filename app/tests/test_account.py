# -*- coding:utf-8 -*-
import time

from .conftest import TestBase
from .contract_modules import *
from ..models import User

from logging import getLogger

logger = getLogger('api')


# 初期設定ユーザ
# [
#      {
#         'login_id': 'admin',
#         'user_name': '管理者',
#         'role_id': 1,
#         'password': '1234'
#     },{
#         'login_id': 'user',
#         'user_name': 'ユーザ',
#         'role_id': 2,
#         'password': '1234'
#     },
# ]

# ユーザ一覧
class TestAccountList(TestBase):
    target_url = '/account/list'
    target_url_404 = '/account/listtttt'

    # ＜正常系１＞
    # 通常参照（管理者ロール）
    def test_normal_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.target_url)
        assert response.status_code == 200
        assert '<title>アカウント一覧'.encode('utf-8') in response.data
        assert '<td><a href="/account/edit/1">admin</a></td>'.encode('utf-8') in response.data
        assert '<td><a href="/account/edit/2">user</a></td>'.encode('utf-8') in response.data

    # ＜エラー系１＞
    # 権限なしエラー
    def test_error_1(self, app):
        client = self.client_with_user_login(app)
        response = client.get(self.target_url)
        assert response.status_code == 403

    # ＜エラー系２＞
    # 権限なしエラー
    def test_error_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.target_url_404)
        assert response.status_code == 404


# ユーザ登録
class TestAccountRegist(TestBase):
    target_url = '/account/regist'

    # ＜正常系１＞
    # 初期表示：GET
    def test_normal_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.target_url)
        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data

    # ＜正常系2＞
    # 登録：POST
    def test_normal_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            '/account/regist',
            data={
                'login_id': 'test_normal',
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 1,
            }
        )
        assert response.status_code == 302

    # ＜エラー系1-1＞
    # 権限エラー：管理者ロール以外での参照（GET）
    def test_error_1_1(self, app):
        client = self.client_with_user_login(app)
        response = client.get('/account/regist')
        assert response.status_code == 403

    # ＜エラー系1-2＞
    # 権限エラー：管理者ロール以外での参照（POST）
    def test_error_1_2(self, app):
        client = self.client_with_user_login(app)
        response = client.post('/account/regist')
        assert response.status_code == 403

    # ＜エラー系2-1＞
    # 登録（POST）：入力値なし（全て）
    def test_error_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.post('/account/regist')
        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data

    # ＜エラー系2-2＞
    # 登録（POST）：入力値なし（login_id）
    def test_error_2_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            '/account/regist',
            data={
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 1,
            }
        )
        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'ログインIDは必須です。'.encode('utf-8') in response.data

    # ＜エラー系2-3＞
    # 登録（POST）：入力値なし（user_name）
    def test_error_2_3(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            '/account/regist',
            data={
                'login_id': 'test_user',
                'icon': '',
                'role': 1,
            }
        )
        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'ユーザー名は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3-1＞
    # 登録（POST）：入力誤り
    # login_idが短い（３文字以下）
    def test_error_3_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            '/account/regist',
            data={
                'login_id': 'abc',
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 1,
            }
        )
        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'ログインIDは4文字以上12文字までです。'.encode('utf-8') in response.data

    # ＜エラー系3-2＞
    # 登録（POST）：入力誤り
    # login_idに半角英数アンダースコア以外の文字が含まれる
    def test_error_3_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            '/account/regist',
            data={
                'login_id': 'abcd?',
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 1,
            }
        )
        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'ログインIDは半角英数アンダースコアのみ使用可能です。'.encode('utf-8') in response.data

    # ＜エラー系4＞
    # 登録（POST）：データ重複エラー
    # 既に登録されているlogin_idを追加登録
    def test_error_4(self, app):
        client = self.client_with_admin_login(app)

        # 1回目
        client.post(
            '/account/regist',
            data={
                'login_id': 'test_user',
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 1,
            }
        )

        # 2回目
        response = client.post(
            '/account/regist',
            data={
                'login_id': 'test_user',
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 1,
            }
        )

        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'このログインIDは既に使用されています。'.encode('utf-8') in response.data

    # ＜エラー系5＞
    # 登録（POST）：存在しないロールを指定
    def test_error_5(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            '/account/regist',
            data={
                'login_id': 'user_error',
                'user_name': 'テストユーザ',
                'icon': '',
                'role': 10,
            }
        )

        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'Not a valid choice'.encode('utf-8') in response.data


# ユーザ更新（管理者）
class TestAccountEdit(TestBase):
    target_url = '/account/edit/'

    # ＜正常系１＞
    # 初期表示：GET
    def test_normal_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.get(self.target_url + '1')
        assert response.status_code == 200
        assert '<title>アカウント編集'.encode('utf-8') in response.data

    # ＜正常系2＞
    # 登録：POST
    def test_normal_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.target_url + '1',
            data={
                'login_id': 'admin',
                'user_name': '管理者',
                'icon': 'xxxx',
                'role': 1,
            }
        )
        assert response.status_code == 302

    # ＜エラー系1＞
    #   登録：POST
    #   入力エラー
    def test_error_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.target_url + '1',
            data={
            }
        )
        assert response.status_code == 200
        assert 'ログインIDは必須です。'.encode('utf-8') in response.data
        assert 'ユーザー名は必須です。'.encode('utf-8') in response.data
        assert 'Not a valid choice'.encode('utf-8') in response.data


# ユーザ更新
class TestAccountEditCurrent(TestBase):
    target_url = '/account/edit_current'

    # ＜正常系１＞
    # 初期表示：GET
    def test_normal_1(self, app):
        client = self.client_with_user_login(app)
        response = client.get(self.target_url)
        assert response.status_code == 200
        assert '<title>アカウント編集'.encode('utf-8') in response.data

    # ＜正常系2＞
    # 登録：POST
    def test_normal_2(self, app):
        client = self.client_with_user_login(app)
        response = client.post(
            self.target_url,
            data={
                'login_id': 'user',
                'user_name': 'ユーザ',
                'icon': 'xxxx'
            }
        )
        assert response.status_code == 302

    # ＜エラー系1＞
    # 登録：POST
    def test_error_1(self, app):
        client = self.client_with_user_login(app)
        response = client.post(
            self.target_url,
            data={}
        )
        assert response.status_code == 200
        assert 'ログインIDは必須です。'.encode('utf-8') in response.data
        assert 'ユーザー名は必須です。'.encode('utf-8') in response.data


# パスワード変更
class TestAccountPwdChg(TestBase):
    target_url = '/account/pwdchg'

    # ＜正常系１＞
    # GET
    def test_normal_1(self, app):
        client = self.client_with_user_login(app)
        response = client.get(self.target_url)
        assert response.status_code == 200
        assert '<title>パスワード変更'.encode('utf-8') in response.data

    # ＜正常系2＞
    # POST
    def test_normal_2(self, app):
        client = self.client_with_user_login(app)
        response = client.post(
            self.target_url,
            data={
                'password': '1234',
                'confirm': '1234'
            }
        )
        assert response.status_code == 302

    # ＜エラー系1＞
    # パスワードなし
    def test_error_1(self, app):
        client = self.client_with_user_login(app)
        response = client.post(
            self.target_url,
            data={
                'confirm': '1234'
            }
        )
        assert response.status_code == 200
        assert '<title>パスワード変更'.encode('utf-8') in response.data
        assert '新しいパスワードが入力されていません。'.encode('utf-8') in response.data

    # ＜エラー系2＞
    # 確認用パスワードが一致しない
    def test_error_2(self, app):
        client = self.client_with_user_login(app)
        response = client.post(
            self.target_url,
            data={
                'password': '1234',
                'confirm': '4321'
            }
        )
        assert response.status_code == 200
        assert '<title>パスワード変更'.encode('utf-8') in response.data
        assert 'パスワードが一致しません。'.encode('utf-8') in response.data


# パスワード初期化
class TestAccountPwdInit(TestBase):
    target_url = '/account/pwdinit'

    # ＜正常系1＞
    # POST
    def test_normal_1(self, db, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.target_url,
            data={
                'id': '2'
            }
        )
        assert response.status_code == 302

        # DB戻し
        user = db.session.query(User).filter(User.id == 2).first()
        user.password = '1234'


# ユーザ削除
class TestAccountDelete(TestBase):
    target_url = '/account/delete'

    # ＜正常系1＞
    # POST
    def test_normal_1(self, db, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.target_url,
            data={
                'login_id': 'user'
            }
        )
        assert response.status_code == 302
        db.session.commit()

        # DB戻し
        user = User()
        user.login_id = 'user'
        user.user_name = 'ユーザ'
        user.role_id = 2
        user.password = '1234'
        db.session.add(user)

    # ＜エラー系1＞
    # 権限エラー
    def test_error_1(self, db, app):
        client = self.client_with_user_login(app)
        response = client.post(
            self.target_url,
            data={
                'login_id': 'user'
            }
        )
        assert response.status_code == 403


# 銀行情報登録
class TestBankInfo(TestBase):
    url_bankinfo = '/account/bankinfo'

    # ＜正常系1＞
    # 通常参照（データなし）
    def test_normal_1(self, app, shared_contract):
        # config登録
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetStraightBondExchange']['address']
        Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS = shared_contract['PaymentGateway']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        client = self.client_with_admin_login(app)
        response = client.get(self.url_bankinfo)
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_name" name="bank_name" type="text" value="">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="bank_code" name="bank_code" type="text" value="">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="branch_name" name="branch_name" type="text" value="">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="branch_code" name="branch_code" type="text" value="">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="account_number" name="account_number" type="text" value="">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="account_holder" name="account_holder" type="text" value="">'.encode(
            'utf-8') in response.data

    # ＜正常系2＞
    # 登録　→　正常参照
    def test_normal_2(self, app, shared_contract):
        register_terms(eth_account['agent'], shared_contract['PaymentGateway'])

        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={
                'name': '株式会社１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０',
                'bank_name': '銀行めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０',
                'bank_code': '0001',
                'branch_name': '支店めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０',
                'branch_code': '100',
                'account_type': 2,
                'account_number': '1234567',
                'account_holder': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ-ﾞﾟｱｲｳｴｵｶｷｸｹｺｱ'
            }
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_name" name="bank_name" type="text" value="銀行めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="bank_code" name="bank_code" type="text" value="0001">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="branch_name" name="branch_name" type="text" value="支店めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="branch_code" name="branch_code" type="text" value="100">'.encode(
            'utf-8') in response.data
        assert '<option selected value="2">当座</option>'.encode('utf-8') in response.data
        assert '<input class="form-control" id="account_number" name="account_number" type="text" value="1234567">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="account_holder" name="account_holder" type="text" value="ABCDEFGHIJKLMNOPQRSTUVWXYZ-ﾞﾟｱｲｳｴｵｶｷｸｹｺｱ">'.encode(
            'utf-8') in response.data

        # 待機
        time.sleep(10)

        # PersonalInfoの確認
        personal_info_json = get_personal_encrypted_info(shared_contract['PersonalInfo'],
                                                         eth_account['issuer']['account_address'],
                                                         eth_account['issuer']['account_address'])
        assert personal_info_json['name'] == ''
        assert personal_info_json['address']['postal_code'] == ''
        assert personal_info_json['address']['prefecture'] == ''
        assert personal_info_json['address']['city'] == ''
        assert personal_info_json['address']['address1'] == ''
        assert personal_info_json['address']['address2'] == ''
        assert personal_info_json['email'] == ''

        # PaymentAccountの確認
        payment_account_json = get_payment_account_encrypted_info(
            shared_contract['PaymentGateway'],
            eth_account['issuer']['account_address'],
            eth_account['agent']['account_address']
        )

    # ＜正常系3＞
    # 通常参照（登録済）
    def test_normal_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_bankinfo)
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data

    # ＜正常系4＞
    # 上書き登録
    def test_normal_4(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={
                'name': '株式会社２３４',
                'bank_name': '銀行めい２３４',
                'bank_code': '0002',
                'branch_name': '支店めい２３４',
                'branch_code': '101',
                'account_type': 4,
                'account_number': '7654321',
                'account_holder': 'ﾃｽﾄ'
            }
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_name" name="bank_name" type="text" value="銀行めい２３４">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="bank_code" name="bank_code" type="text" value="0002">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="branch_name" name="branch_name" type="text" value="支店めい２３４">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="branch_code" name="branch_code" type="text" value="101">'.encode(
            'utf-8') in response.data
        assert '<option selected value="4">貯蓄預金</option>'.encode('utf-8') in response.data
        assert '<input class="form-control" id="account_number" name="account_number" type="text" value="7654321">'.encode(
            'utf-8') in response.data
        assert '<input class="form-control" id="account_holder" name="account_holder" type="text" value="ﾃｽﾄ">'.encode(
            'utf-8') in response.data

        # 待機
        time.sleep(10)

        # personalInfoの確認
        personal_info_json = get_personal_encrypted_info(
            shared_contract['PersonalInfo'],
            eth_account['issuer']['account_address'],
            eth_account['issuer']['account_address']
        )
        assert personal_info_json['name'] == ''
        assert personal_info_json['address']['postal_code'] == ''
        assert personal_info_json['address']['prefecture'] == ''
        assert personal_info_json['address']['city'] == ''
        assert personal_info_json['address']['address1'] == ''
        assert personal_info_json['address']['address2'] == ''

        # PaymentAccountの確認
        payment_account_json = get_payment_account_encrypted_info(
            shared_contract['PaymentGateway'],
            eth_account['issuer']['account_address'],
            eth_account['agent']['account_address']
        )

    # ＜エラー系1-1＞
    # 必須系
    def test_error_1_1(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={}
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '金融機関名は必須です。'.encode('utf-8') in response.data
        assert '金融機関コードは必須です。'.encode('utf-8') in response.data
        assert '支店名は必須です。'.encode('utf-8') in response.data
        assert '支店コードは必須です。'.encode('utf-8') in response.data
        assert '口座番号は必須です。'.encode('utf-8') in response.data
        assert '口座名義は必須です。'.encode('utf-8') in response.data

    # ＜エラー系1-2＞
    # 桁数系(1文字オーバー)
    def test_error_1_2(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={
                'name': '１２３４５６７８９０あいうえおかきくけこ１２３４５６７８９０さしすせそたちつてとあ',  # 41文字
                'bank_name': '１２３４５６７８９０あいうえおかきくけこ１２３４５６７８９０さしすせそたちつてとあ',  # 41文字
                'bank_code': '00067',
                'branch_name': '１２３４５６７８９０あいうえおかきくけこ１２３４５６７８９０さしすせそたちつてとあ',  # 41文字
                'branch_code': '1017',
                'account_number': '12345678',
                'account_holder': '12345678901234567890123456789012345678901',  # 41文字
            }
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '金融機関名は40文字までです。'.encode('utf-8') in response.data
        assert '金融機関コードは4桁です。'.encode('utf-8') in response.data
        assert '支店名は40文字までです。'.encode('utf-8') in response.data
        assert '支店コードは3桁です。'.encode('utf-8') in response.data
        assert '口座番号は7桁です。'.encode('utf-8') in response.data
        assert '口座名義は40文字までです。'.encode('utf-8') in response.data

    # ＜エラー系1-3＞
    # 桁数系(1文字少ない)
    def test_error_1_3(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={
                'name': '１２３４５６７８９０あいうえおかきくけこ１２３４５６７８９０さしすせそたちつて',  # 39文字（正常）
                'bank_name': '１２３４５６７８９０あいうえおかきくけこ１２３４５６７８９０さしすせそたちつて',  # 39文字（正常）
                'bank_code': '001',  # 3文字
                'branch_name': '１２３４５６７８９０あいうえおかきくけこ１２３４５６７８９０さしすせそたちつて',  # 39文字（正常）
                'branch_code': '10',  # 2文字
                'account_number': '123456',  # 6文字
                'account_holder': '123456789012345678901234567890123456789',  # 39文字（正常）
            }
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '会社名は40文字までです。'.encode('utf-8') not in response.data
        assert '金融機関名は40文字までです。'.encode('utf-8') not in response.data
        assert '金融機関コードは4桁です。'.encode('utf-8') in response.data
        assert '支店名は40文字までです。'.encode('utf-8') not in response.data
        assert '支店コードは3桁です。'.encode('utf-8') in response.data
        assert '口座番号は7桁です。'.encode('utf-8') in response.data
        assert '口座名義は40文字までです。'.encode('utf-8') not in response.data

    # ＜エラー系1-4＞
    # 入力不可文字
    def test_error_1_4(self, app):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={
                'bank_code': '00b1',  # 数字以外
                'branch_code': '1c0',  # 数字以外
                'account_number': '1234d56',  # 数字以外
                'account_holder': 'テスト',  # 全角カナ
            }
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '金融機関コードは数字のみです。'.encode('utf-8') in response.data
        assert '支店コードは数字のみです。'.encode('utf-8') in response.data
        assert '口座番号は数字のみです。'.encode('utf-8') in response.data
        assert '口座名義は半角カナ文字（大文字）、半角英数字、一部の記号のみです。'.encode('utf-8') in response.data

    # ＜エラー系2_1＞
    # 権限なしエラー
    def test_error_2_1(self, app):
        client = self.client_with_user_login(app)
        response = client.get(self.url_bankinfo)
        assert response.status_code == 403
