# -*- coding:utf-8 -*-
import json

from .conftest import TestBase


class TestAPIAuth(TestBase):

    target_url = '/api/auth'

    ##########################################################################
    # 正常系
    ##########################################################################

    # ＜正常系1＞
    #   API認証
    def test_normal_1(self, app):
        with app.test_client() as client:
            response = client.post(
                self.target_url,
                json={
                    'login_id': 'user',
                    'password': '1234'
                }
            )
            assert response.status_code == 200
            assert response.data is not None

    ##########################################################################
    # エラー系
    ##########################################################################

    # ＜エラー系1＞
    #   API認証エラー
    def test_error_1(self, app):
        with app.test_client() as client:
            response = client.post(
                self.target_url,
                json={}
            )
            assert response.status_code == 401
            assert json.loads(response.data.decode('utf-8')) == {
                "description": "Invalid credentials",
                "error": "Bad Request",
                "status_code": 401
            }
