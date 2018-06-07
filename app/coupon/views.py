# -*- coding:utf-8 -*-
import secrets
import datetime
import json
import time
import base64
from base64 import b64encode

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from flask import Flask, request, redirect, url_for, flash, session
from flask_restful import Resource, Api
from flask import render_template
from flask import jsonify, abort
from flask_login import login_required, current_user
from flask import Markup, jsonify
from flask import current_app

from web3 import Web3
from eth_utils import to_checksum_address
from solc import compile_source
from sqlalchemy import desc

from . import coupon
from .. import db
from ..models import Role, User, Token, Certification
from .forms import *
from ..decorators import admin_required
from config import Config

from logging import getLogger
logger = getLogger('api')

from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

#+++++++++++++++++++++++++++++++
# Utils
#+++++++++++++++++++++++++++++++
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')

####################################################
# クーポン
####################################################
# クーポン発行
@coupon.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('coupon/issue')
    form = IssueCouponForm()
    if request.method == 'POST':
        if form.validate():
            # token = Token.query.filter(Token.token_address==form.tokenAddress.data).first()
            # token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

            # TokenContract = web3.eth.contract(
            #     address= token.token_address,
            #     abi = token_abi
            # )

            # web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
            # gas = TokenContract.estimateGas().transfer(to_checksum_address(form.sendAddress.data), form.sendAmount.data)
            # TokenContract.functions.transfer(to_checksum_address(form.sendAddress.data), form.sendAmount.data).transact(
            #     {'from':Config.ETH_ACCOUNT, 'gas':gas}
            # )

            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/transfer.html', form=form)
        else:
            flash_errors(form)
            return render_template('coupon/transfer.html', form=form)
    else: # GET
        return render_template('coupon/transfer.html', form=form)

# クーポン割当
@coupon.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    logger.info('coupon/transfer')
    form = TransferCouponForm()
    if request.method == 'POST':
        if form.validate():
            token = Token.query.filter(Token.token_address==form.tokenAddress.data).first()
            token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

            TokenContract = web3.eth.contract(
                address= token.token_address,
                abi = token_abi
            )

            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
            gas = TokenContract.estimateGas().transfer(to_checksum_address(form.sendAddress.data), form.sendAmount.data)
            TokenContract.functions.transfer(to_checksum_address(form.sendAddress.data), form.sendAmount.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )

            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/transfer.html', form=form)
        else:
            flash_errors(form)
            return render_template('coupon/transfer.html', form=form)
    else: # GET
        return render_template('coupon/transfer.html', form=form)