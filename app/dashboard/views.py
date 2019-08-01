# -*- coding:utf-8 -*-
import datetime
import traceback

from flask import request, redirect, url_for, flash
from flask import render_template
from flask_login import login_required

from . import dashboard
from .. import db
from ..util import *
from .forms import *
from config import Config
from app.contracts import Contract

from logging import getLogger

logger = getLogger('api')

from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


def token_list(TEMPLATE_ID_SB):
    pass


@dashboard.route('/main', methods=['GET'])
@login_required
def main():
    logger.info('dashboard/main')

    # 発行済社債トークンの情報をDBから取得する
    sb_tokens = token_list(Config.TEMPLATE_ID_SB)
    coupon_tokens = token_list(Config.TEMPLATE_ID_COUPON)
    membership_tokens = token_list(Config.TEMPLATE_ID_MEMBERSHIP)

    return render_template('dashboard/main.html', sb_tokens=sb_tokens, coupon_tokens=coupon_tokens,
                           membership_tokens=membership_tokens)


def token_list(template_id):
    tokens = Token.query.filter_by(template_id=template_id).all()
    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address == None:
                name = '<処理中>'
                symbol = '<処理中>'
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
                totalSupply = TokenContract.functions.totalSupply().call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'totalSupply': totalSupply
            })
        except Exception as e:
            logger.error(e)
            pass

        try:
            # Exchange-Contractへの接続
            ExchangeContract = web3.eth.contract(
                address=Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS,
                abi=json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            )
            # for debug
            logger.info(ExchangeContract.abi)

            # Token-Contractから情報を取得する
            last_price = ExchangeContract.functions.lastPrice(row.token_address).call()

            token_list.append({
                'last_price': last_price
            })

        except Exception as e:
            logger.error(e)
            pass

    return token_list