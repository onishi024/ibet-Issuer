"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

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
