# -*- coding:utf-8 -*-
import pytest
import json
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from config import Config
from .conftest import TestBase
from .utils.account_config import eth_account
from .utils.contract_utils_common import processor_issue_event, index_transfer_event, clean_issue_event
from .utils.contract_utils_personal_info import register_personal_info


class TestShare(TestBase):
    #############################################################################
    # テスト対象URL
    #############################################################################
    url_list = '/share/list'  # 発行済一覧
    url_issue = '/share/issue'  # 新規発行

    #############################################################################
    # 共通処理
    #############################################################################
    @pytest.fixture(autouse=True)
    def clear_db(self, shared_contract, db):
        yield

        # 後処理
        clean_issue_event(db)

    #############################################################################
    # テスト（正常系）
    #############################################################################
    # ＜正常系1＞
    #   新規発行画面表示
    def test_normal_1(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 初期表示
        response = client.get(self.url_issue)

        assert response.status_code == 200
        assert '<title>株式新規発行'.encode('utf-8') in response.data

    # ＜正常系2＞
    #   新規発行実施
    def test_normal_2(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テスト会社株',
                'symbol': 'SHARE',
                'totalSupply': 1000000,
                'issuePrice': 1000,
                'dividends': 100,
                'dividendRecordDate': '20200401',
                'dividendPaymentDate': '20200501',
                'cansellationDate': '20200601',
                'transferable': 'True',
                'memo': 'メモ',
                'referenceUrls_1': 'http://example.com',
                'referenceUrls_2': 'http://image.png',
                'referenceUrls_3': '',
                'contact_information': '問い合わせ先',
                'privacy_policy': 'プライバシーポリシー',
                'tradableExchange': shared_contract['IbetShareExchange']['address'],
                'personalInfoAddress': shared_contract['PersonalInfo']['address'],
            }
        )
        assert response.status_code == 302
        assert response.headers.get('Location').endswith(self.url_list)

    #############################################################################
    # テスト（エラー系）
    #############################################################################

    # ＜エラー系1＞
    #   株式新規発行（必須エラー）
    def test_error_1(self, app):
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
        assert '消却日は必須です。'.encode('utf-8') in response.data
        assert 'DEXアドレスは必須です。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは必須です。'.encode('utf-8') in response.data

    # ＜エラー系2＞
    #   株式新規発行（アドレスのフォーマットエラー）
    def test_error_1_2(self, app):
        error_address = '0xc94b0d702422587e361dd6cd08b55dfe1961181f1'

        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テスト会社株',
                'symbol': 'SHARE',
                'totalSupply': 1000000,
                'issuePrice': 1000,
                'dividends': 100,
                'dividendRecordDate': '20200401',
                'dividendPaymentDate': '20200501',
                'cansellationDate': '20200601',
                'transferable': 'True',
                'memo': 'メモ',
                'referenceUrls_1': 'http://example.com',
                'referenceUrls_2': 'http://image.png',
                'referenceUrls_3': '',
                'contact_information': '問い合わせ先',
                'privacy_policy': 'プライバシーポリシー',
                'tradableExchange': error_address,
                'personalInfoAddress': error_address,
            }
        )
        assert response.status_code == 200
        assert '<title>株式新規発行'.encode('utf-8') in response.data
        assert 'DEXアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
        assert '個人情報コントラクトアドレスは有効なアドレスではありません。'.encode('utf-8') in response.data
