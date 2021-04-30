"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

import json
from typing import Optional

from flask import abort
from web3 import Web3
from web3.middleware import geth_poa_middleware

from config import Config
from logging import getLogger
logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


class TokenUtils:

    @staticmethod
    def get_contract(token_address: str, issuer_address: Optional[str], template_id: int = None):
        """トークンコントラクト取得

        :param token_address: トークンアドレス
        :param issuer_address: トークン発行体アドレス。ログインユーザごとに参照できるトークンを制限するために使用する。
            Indexer/processor等でログインユーザによる制限が不要な場合はNoneを指定する。
        :param template_id:
            （任意項目）　テンプレートID（例 :py:attr:`.Config.TEMPLATE_ID_SB` ）。
            トークンの種類を限定したいときに設定する。たとえば、債券専用の処理にクライアントが誤って
            会員権のトークンアドレスを送信し、そのまま間違った処理が実行されることを防ぎたい場合に設定する。
            テンプレートID指定するとトークンアドレスとテンプレートIDの組み合わせが正しくない場合にエラーとなる。
        :return: コントラクト
        :raises HTTPException:
            トークンアドレスが未登録の場合、
            トークンアドレスとテンプレートIDの組み合わせが正しくない場合（テンプレートID指定時のみ）、
            HTTPステータス404で例外を発生させる。
        """
        from app.models import Token

        token_query = Token.query.filter(Token.token_address == token_address)
        if issuer_address is not None:
            # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
            token_query = token_query.filter(Token.admin_address == issuer_address.lower())
        if template_id is not None:
            token_query = token_query.filter(Token.template_id == template_id)
        token = token_query.first()

        if token is None:
            abort(404)
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        return web3.eth.contract(address=token.token_address, abi=token_abi)
