# -*- coding:utf-8 -*-
from flask import url_for

from .conftest import TestBase


class TestAuth(TestBase):

    ##########################################################################
    # 正常系
    ##########################################################################

    # ＜正常系1＞
    #   ログイン
    def test_normal_1(self, app):
        client = app.test_client()
        response = client.post(
            url_for('auth.login'),
            data={
                'login_id': 'user',
                'password': '1234'
            }
        )

        assert response.status_code == 302

    # ＜正常系2＞
    #   ログアウト
    def test_normal_2(self, app):
        client = app.test_client()

        # ログイン
        response = client.post(
            url_for('auth.login'),
            data={
                'login_id': 'user',
                'password': '1234'
            }
        )
        assert response.status_code == 302

        # ログアウト
        response = client.post(url_for('auth.logout'), data={})
        assert response.status_code == 302

    ##########################################################################
    # エラー系
    ##########################################################################

    # ＜エラー系1_1＞
    #   ログイン：認証失敗（パスワード誤り）
    def test_error_1_1(self, app):
        client = app.test_client()
        response = client.post(
            url_for('auth.login'),
            data={
                'login_id': 'user',
                'password': '4321'
            }
        )

        assert response.status_code == 200
        assert 'ログインID又はパスワードが正しくありません。'.encode('utf-8') in response.data

    # ＜エラー系1_2＞
    #   ログイン：認証失敗（ログインIDが存在しない）
    def test_error_1_2(self, app):
        client = app.test_client()
        response = client.post(
            url_for('auth.login'),
            data={
                'login_id': 'useruser',
                'password': '1234'
            }
        )

        assert response.status_code == 200
        assert 'ログインID又はパスワードが正しくありません。'.encode('utf-8') in response.data

    # ＜エラー系1_＞
    #   ログイン：認証失敗（ログインIDが空のため form.validate() == False）
    def test_error_1_3(self, app):
        client = app.test_client()
        response = client.post(
            url_for('auth.login'),
            data={
                'login_id': '',
                'password': '1234'
            }
        )

        assert response.status_code == 200
        assert 'ログインIDを入力してください。。'.encode('utf-8') in response.data
