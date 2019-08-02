# -*- coding:utf-8 -*-
from flask import render_template
from flask_login import login_required

from . import dashboard
from ..util import *
from config import Config
from app.contracts import Contract

from logging import getLogger
logger = getLogger('api')

from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


@dashboard.route('/main', methods=['GET'])
@login_required
def main():
    logger.info('dashboard/main')
    coupon_tokens = token_list_coupon(Config.TEMPLATE_ID_COUPON)
    membership_tokens = token_list_membership(Config.TEMPLATE_ID_MEMBERSHIP)

    return render_template(
        'dashboard/main.html',
        coupon_tokens=coupon_tokens,
        membership_tokens=membership_tokens
    )


def token_list_membership(template_id):
    tokens = Token.query.filter_by(template_id=template_id).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                total_supply = None
                last_price = None
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

                # 現在値の取得
                ExchangeContract = Contract.get_contract(
                    'IbetMembershipExchange',
                    Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
                )
                last_price = ExchangeContract.functions.lastPrice(row.token_address).call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'total_supply': total_supply,
                'last_price': last_price
            })

        except Exception as e:
            logger.error(e)
            pass

    return token_list


def token_list_coupon(template_id):
    tokens = Token.query.filter_by(template_id=template_id).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                total_supply = None
                last_price = None
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

                # Exchange-Contractへの接続
                ExchangeContract = Contract.get_contract(
                    'IbetCouponExchange',
                    Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
                )

                # Token-Contractから情報を取得する
                last_price = ExchangeContract.functions.lastPrice(row.token_address).call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'total_supply': total_supply,
                'last_price': last_price
            })

        except Exception as e:
            logger.error(e)
            pass

    return token_list
