# -*- coding:utf-8 -*-
import pytest
import os
import time

from .conftest import TestBase
from .account_config import eth_account
from config import Config
from .contract_modules import *

from logging import getLogger
logger = getLogger('api')

class TestBankInfo(TestBase):
    url_bankinfo = '/account/bankinfo'

    # ＜正常系１＞
    # 通常参照（データなし）
    def test_normal_1(self, app, shared_contract):
        # config登録
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetStraightBondExchange']['address']
        Config.WHITE_LIST_CONTRACT_ADDRESS = shared_contract['WhiteList']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        client = self.client_with_admin_login(app)
        response = client.get(self.url_bankinfo)
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '<input class="form-control" id="name" name="name" type="text" value="">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_name" name="bank_name" type="text" value="">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_code" name="bank_code" type="text" value="">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="branch_name" name="branch_name" type="text" value="">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="branch_code" name="branch_code" type="text" value="">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="account_number" name="account_number" type="text" value="">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="account_holder" name="account_holder" type="text" value="">'.encode('utf-8') in response.data

    # ＜正常系２＞
    # 登録　→　正常参照
    def test_normal_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_bankinfo,
            data={
                'name':'株式会社１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０',
                'bank_name':'銀行めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０',
                'bank_code':'0001',
                'branch_name':'支店めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０',
                'branch_code':'100',
                'account_type':'2',
                'account_number':'1234567',
                'account_holder':'ABCDEFGHIJKLMNOPQRSTUVWXYZ-ﾞﾟｱｲｳｴｵｶｷｸｹｺｱ' 
            }
        )
        assert response.status_code == 200
        assert '<title>銀行情報登録'.encode('utf-8') in response.data
        assert '<input class="form-control" id="name" name="name" type="text" value="株式会社１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_name" name="bank_name" type="text" value="銀行めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="bank_code" name="bank_code" type="text" value="0001">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="branch_name" name="branch_name" type="text" value="支店めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="branch_code" name="branch_code" type="text" value="100">'.encode('utf-8') in response.data
        assert '<option selected value="2">当座</option>'.encode('utf-8') in response.data
        assert '<input class="form-control" id="account_number" name="account_number" type="text" value="1234567">'.encode('utf-8') in response.data
        assert '<input class="form-control" id="account_holder" name="account_holder" type="text" value="ABCDEFGHIJKLMNOPQRSTUVWXYZ-ﾞﾟｱｲｳｴｵｶｷｸｹｺｱ">'.encode('utf-8') in response.data

        # 待機
        time.sleep(4)
        
        # personalInfoの確認
        personal_info_json = get_personal_encrypted_info(shared_contract['PersonalInfo'], eth_account['issuer']['account_address'], eth_account['issuer']['account_address'])
        assert personal_info_json['name'] == '株式会社１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０'
        assert personal_info_json['address']['postal_code'] == ''
        assert personal_info_json['address']['prefecture'] == ''
        assert personal_info_json['address']['city'] == ''
        assert personal_info_json['address']['address1'] == ''
        assert personal_info_json['address']['address2'] == ''
        assert personal_info_json['bank_account']['bank_name'] == '銀行めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０'
        assert personal_info_json['bank_account']['bank_code'] == '0001'
        assert personal_info_json['bank_account']['branch_office'] == '支店めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０'
        assert personal_info_json['bank_account']['branch_code'] == '100'
        assert personal_info_json['bank_account']['account_type'] == '2'
        assert personal_info_json['bank_account']['account_number'] == '1234567'
        assert personal_info_json['bank_account']['account_holder'] == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ-ﾞﾟｱｲｳｴｵｶｷｸｹｺｱ'

        # whitelistの確認
        whitelist_json = get_whitelist_encrypted_info(shared_contract['WhiteList'], eth_account['issuer']['account_address'], eth_account['agent']['account_address'])
        assert whitelist_json['name'] == '株式会社１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０'
        assert whitelist_json['bank_account']['bank_name'] == '銀行めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０'
        assert whitelist_json['bank_account']['bank_code'] == '0001'
        assert whitelist_json['bank_account']['branch_office'] == '支店めい１２３４５あいうえおかきくけこさしすせそたちつてと１２３４５６７８９０'
        assert whitelist_json['bank_account']['branch_code'] == '100'
        assert whitelist_json['bank_account']['account_type'] == '2'
        assert whitelist_json['bank_account']['account_number'] == '1234567'
        assert whitelist_json['bank_account']['account_holder'] == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ-ﾞﾟｱｲｳｴｵｶｷｸｹｺｱ'

    # # ＜正常系３＞
    # # 上書き登録
    # def test_normal_3(self, app):
    #     client = self.client_with_admin_login(app)
    #     response = client.post(
    #         '/account/bankinfo',
    #         data={
    #             'irainin_code':'2087654321',
    #             'irainin_name':'ｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾜｦﾝ', # A-Z0-9ｱ-ﾝﾞﾟ\-
    #             'bank_code':'0006',
    #             'branch_code':'101',
    #             'koza_no':'1234568',
    #         }
    #     )
    #     assert response.status_code == 200
    #     assert '<title>銀行情報登録'.encode('utf-8') in response.data
    #     assert '<input class="form-control" id="irainin_code" name="irainin_code" type="text" value="2087654321">'.encode('utf-8') in response.data
    #     assert '<input class="form-control" id="irainin_name" name="irainin_name" type="text" value="ｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾜｦﾝ">'.encode('utf-8') in response.data
    #     assert '<input class="form-control" id="bank_code" name="bank_code" type="text" value="0006">'.encode('utf-8') in response.data
    #     assert '<input class="form-control" id="branch_code" name="branch_code" type="text" value="101">'.encode('utf-8') in response.data
    #     assert '<input class="form-control" id="koza_no" name="koza_no" type="text" value="1234568">'.encode('utf-8') in response.data


    # # ＜エラー系1-1＞
    # # 必須系
    # def test_error_1_1(self, app):
    #     client = self.client_with_admin_login(app)
    #     response = client.post(
    #         '/account/bankinfo',
    #         data={}
    #     )
    #     assert response.status_code == 200
    #     assert '<title>銀行情報登録'.encode('utf-8') in response.data
    #     assert '振込依頼人コード（委託者コード）は必須です。'.encode('utf-8') in response.data
    #     assert '振込依頼人名は必須です。'.encode('utf-8') in response.data
    #     assert '金融機関コードは必須です。'.encode('utf-8') in response.data
    #     assert '支店コードは必須です。'.encode('utf-8') in response.data
    #     assert '口座番号は必須です。'.encode('utf-8') in response.data


    # # ＜エラー系1-2＞
    # # 桁数系(1文字オーバー)
    # def test_error_1_2(self, app):
    #     client = self.client_with_admin_login(app)
    #     response = client.post(
    #         '/account/bankinfo',
    #         data={
    #             'irainin_code':'20876543211', # 11文字
    #             'irainin_name':'12345678901234567890123456789012345678901', # 41文字
    #             'bank_code':'00067',
    #             'branch_code':'1017',
    #             'koza_no':'12345687',
    #         }
    #     )
    #     assert response.status_code == 200
    #     assert '<title>銀行情報登録'.encode('utf-8') in response.data
    #     assert '振込依頼人コード（委託者コード）は10文字です。'.encode('utf-8') in response.data
    #     assert '振込依頼人名は40文字までです。'.encode('utf-8') in response.data
    #     assert '金融機関コードは4桁です。'.encode('utf-8') in response.data
    #     assert '支店コードは3桁です。'.encode('utf-8') in response.data
    #     assert '口座番号は7桁です。'.encode('utf-8') in response.data


    # # ＜エラー系1-3＞
    # # 桁数系(1文字少ない)
    # def test_error_1_3(self, app):
    #     client = self.client_with_admin_login(app)
    #     response = client.post(
    #         '/account/bankinfo',
    #         data={
    #             'irainin_code':'208765432', # 9文字
    #             'irainin_name':'123456789012345678901234567890123456789', # 39文字（正常）
    #             'bank_code':'001', # 3文字
    #             'branch_code':'10', # 2文字
    #             'koza_no':'123456', # 6文字
    #         }
    #     )
    #     assert response.status_code == 200
    #     assert '<title>銀行情報登録'.encode('utf-8') in response.data
    #     assert '振込依頼人コード（委託者コード）は10文字です。'.encode('utf-8') in response.data
    #     assert '振込依頼人名は40文字までです。'.encode('utf-8') not in response.data # エラーがないこと。
    #     assert '金融機関コードは4桁です。'.encode('utf-8') in response.data
    #     assert '支店コードは3桁です。'.encode('utf-8') in response.data
    #     assert '口座番号は7桁です。'.encode('utf-8') in response.data


    # # ＜エラー系1-4＞
    # # 入力不可文字
    # def test_error_1_4(self, app):
    #     client = self.client_with_admin_login(app)
    #     response = client.post(
    #         '/account/bankinfo',
    #         data={
    #             'irainin_code':'20123a5678', # 数字以外
    #             'irainin_name':'123456789012345678901234567890123456789a', # A-Z0-9ｱ-ﾝﾞﾟ\-以外
    #             'bank_code':'00b1', # 数字以外
    #             'branch_code':'1c0', # 数字以外
    #             'koza_no':'1234d56', # 数字以外
    #         }
    #     )
    #     assert response.status_code == 200
    #     assert '<title>銀行情報登録'.encode('utf-8') in response.data
    #     assert '振込依頼人コード（委託者コード）は数字のみです。'.encode('utf-8') in response.data
    #     assert '振込依頼人名は半角カナ文字（大文字）および英数字のみです。'.encode('utf-8') in response.data
    #     assert '金融機関コードは数字のみです。'.encode('utf-8') in response.data
    #     assert '支店コードは数字のみです。'.encode('utf-8') in response.data
    #     assert '口座番号は数字のみです。'.encode('utf-8') in response.data


    # ＜エラー系2_1＞
    # 権限なしエラー
    def test_error_2_1(self, app):
        client = self.client_with_user_login(app)
        response = client.get(self.url_bankinfo)
        assert response.status_code == 403
