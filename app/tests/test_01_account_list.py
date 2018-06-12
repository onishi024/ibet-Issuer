# -*- coding:utf-8 -*-
import pytest

from .conftest import TestBase

class TestAccountList(TestBase):

    target_url = '/account/list'

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
