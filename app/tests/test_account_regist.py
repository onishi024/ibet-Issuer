# -*- coding:utf-8 -*-
import pytest

from .conftest import TestBase

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
                'login_id':'test_normal',
                'user_name':'テストユーザ',
                'icon':'',
                'role':1,
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
                'user_name':'テストユーザ',
                'icon':'',
                'role':1,
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
                'login_id':'test_user',
                'icon':'',
                'role':1,
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
                'login_id':'abc',
                'user_name':'テストユーザ',
                'icon':'',
                'role':1,
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
                'login_id':'abcd?',
                'user_name':'テストユーザ',
                'icon':'',
                'role':1,
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
        response = client.post(
            '/account/regist',
            data={
                'login_id':'test_user',
                'user_name':'テストユーザ',
                'icon':'',
                'role':1,
            }
        )

        # 2回目
        response = client.post(
            '/account/regist',
            data={
                'login_id':'test_user',
                'user_name':'テストユーザ',
                'icon':'',
                'role':1,
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
                'login_id':'user_error',
                'user_name':'テストユーザ',
                'icon':'',
                'role':10,
            }
        )

        assert response.status_code == 200
        assert '<title>アカウント追加'.encode('utf-8') in response.data
        assert 'Not a valid choice'.encode('utf-8') in response.data
