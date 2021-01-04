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

from flask import render_template, jsonify, session
from flask_login import login_required

from . import dashboard
from config import Config
from app.utils import ContractUtils

from logging import getLogger

from ..models import Token

logger = getLogger('api')

from web3 import Web3
from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


@dashboard.route('/main', methods=['GET'])
@login_required
def main():
    logger.info('dashboard/main')

    return render_template(
        'dashboard/main.html',
        Config=Config
    )


@dashboard.route('/token_list_share', methods=['GET'])
@login_required
def token_list_share():
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_SHARE,
        # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
        admin_address=session["eth_account"].lower()
    ).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                dividend_record_date = '--'
                cancellation_date = '--'
                total_supply = 0
            else:
                # Token-Contractへの接続
                TokenContract = web3.eth.contract(
                    address=row.token_address,
                    abi=json.loads(
                        row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                )

                # Token-Contractから情報を取得する
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                _, dividend_record_date, _ = TokenContract.functions.dividendInformation().call()
                if dividend_record_date != "":
                    dividend_record_date = dividend_record_date[:4] + '/' + dividend_record_date[4:6] + \
                                           '/' + dividend_record_date[6:]
                cancellation_date = TokenContract.functions.cancellationDate().call()
                if cancellation_date != "":
                    cancellation_date = cancellation_date[:4] + '/' + cancellation_date[4:6] + \
                                        '/' + cancellation_date[6:]
                total_supply = TokenContract.functions.totalSupply().call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'dividend_record_date': dividend_record_date,
                'cancellation_date': cancellation_date,
                'total_supply': total_supply
            })

        except Exception as e:
            logger.exception(e)
            pass
    return jsonify(token_list)


@dashboard.route('/token_list_bond', methods=['GET'])
@login_required
def token_list_bond():
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_SB,
        # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
        admin_address=session["eth_account"].lower()
    ).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                redemption_date = '--'
                total_supply = 0
            else:
                # Token-Contractへの接続
                TokenContract = web3.eth.contract(
                    address=row.token_address,
                    abi=json.loads(
                        row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                )

                # Token-Contractから情報を取得する
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                redemption_date = TokenContract.functions.redemptionDate().call()
                if redemption_date != "":
                    redemption_date = redemption_date[:4] + '/' + redemption_date[4:6] + '/' + redemption_date[6:]
                total_supply = TokenContract.functions.totalSupply().call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'redemption_date': redemption_date,
                'total_supply': total_supply
            })

        except Exception as e:
            logger.exception(e)
            pass
    return jsonify(token_list)


@dashboard.route('/token_list_membership', methods=['GET'])
@login_required
def token_list_membership():
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_MEMBERSHIP,
        # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
        admin_address=session["eth_account"].lower()
    ).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                last_price = 0
                total_supply = 0
            else:
                # Token-Contractへの接続
                TokenContract = web3.eth.contract(
                    address=row.token_address,
                    abi=json.loads(
                        row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                )

                # Token-Contractから情報を取得する
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                total_supply = TokenContract.functions.totalSupply().call()
                tradable_exchange = TokenContract.functions.tradableExchange().call()

                # 現在値の取得
                ExchangeContract = ContractUtils.get_contract(
                    'IbetMembershipExchange',
                    tradable_exchange
                )
                last_price = ExchangeContract.functions.lastPrice(row.token_address).call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'last_price': last_price,
                'total_supply': total_supply
            })

        except Exception as e:
            logger.exception(e)
            pass
    return jsonify(token_list)


@dashboard.route('/token_list_coupon', methods=['GET'])
@login_required
def token_list_coupon():
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_COUPON,
        # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
        admin_address=session["eth_account"].lower()
    ).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                last_price = 0
                total_supply = 0
            else:
                # Token-Contractへの接続
                TokenContract = web3.eth.contract(
                    address=row.token_address,
                    abi=json.loads(
                        row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                )

                # Token-Contractから情報を取得する
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                total_supply = TokenContract.functions.totalSupply().call()
                tradable_exchange = TokenContract.functions.tradableExchange().call()

                # Exchange-Contractへの接続
                ExchangeContract = ContractUtils.get_contract(
                    'IbetCouponExchange',
                    tradable_exchange
                )

                # Token-Contractから情報を取得する
                last_price = ExchangeContract.functions.lastPrice(row.token_address).call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'last_price': last_price,
                'total_supply': total_supply
            })

        except Exception as e:
            logger.exception(e)
            pass
    return jsonify(token_list)
