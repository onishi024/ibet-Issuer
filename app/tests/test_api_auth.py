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
