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

# トランザクションがブロックに取り込まれるまで待つ
# 10秒以上経過した場合は失敗とみなす（Falseを返す）
def wait_transaction_receipt(tx_hash):
    count = 0
    tx = None

    while True:
        time.sleep(0.1)
        try:
            tx = web3.eth.getTransactionReceipt(tx_hash)
        except:
            continue

        count += 1
        if tx is not None:
            break
        elif count > 120:
            raise Exception

    return tx
####################################################
# クーポン
####################################################
# クーポン一覧
@coupon.route('/list', methods=['GET', 'POST'])
@login_required
def list():
    logger.info('coupon/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()

    token_list = []
    for row in tokens:
        is_redeemed = False

        # トークンがデプロイ済みの場合、トークン情報を取得する
        if row.token_address == None:
            name = '<処理中>'
            symbol = '<処理中>'
        else:
            # Token-Contractへの接続
            TokenContract = web3.eth.contract(
                address=row.token_address,
                abi = json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            )

            # Token-Contractから情報を取得する
            name = TokenContract.functions.name().call()
            symbol = TokenContract.functions.symbol().call()
            is_valid = TokenContract.functions.isValid().call()

        token_list.append({
            'name':name,
            'symbol':symbol,
            'is_valid':is_valid,
            'created':row.created,
            'tx_hash':row.tx_hash,
            'token_address':row.token_address
        })

    return render_template('coupon/list.html', tokens=token_list)

# クーポン発行
@coupon.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('coupon/issue')
    form = IssueCouponForm()
    if request.method == 'POST':
        if form.validate():
            ####### トークン発行処理 #######
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

            abi = json.loads(Config.IBET_COUPON_CONTRACT_ABI)
            bytecode = Config.IBET_COUPON_CONTRACT_BYTECODE
            bytecode_runtime = Config.IBET_COUPON_CONTRACT_BYTECODE_RUNTIME

            CouponContract = web3.eth.contract(
                abi = abi,
                bytecode = bytecode,
                bytecode_runtime = bytecode_runtime,
            )

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                form.details.data,
                form.memo.data,
                form.expirationDate.data,
                form.transferable.data
            ]
            tx_hash = CouponContract.deploy(
                transaction={'from':Config.ETH_ACCOUNT, 'gas':4000000},
                args=arguments
            ).hex()

            token = Token()
            token.template_id = Config.TEMPLATE_ID_COUPON
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            ####### 画像URL登録処理 #######
            if form.image_small.data != '' or form.image_medium.data != '' or form.image_large.data != '':
                tx_receipt = wait_transaction_receipt(tx_hash)
                if tx_receipt is not None :
                    contract_address = tx_receipt['contractAddress']
                    CouponContract = web3.eth.contract(
                        address= tx_receipt['contractAddress'],
                        abi = abi
                    )
                    if form.image_small.data != '':
                        gas = CouponContract.estimateGas().setImageURL(0, form.image_small.data)
                        txid_small = CouponContract.functions.setImageURL(0, form.image_small.data).transact(
                            {'from':Config.ETH_ACCOUNT, 'gas':gas}
                        )
                    if form.image_medium.data != '':
                        gas = CouponContract.estimateGas().setImageURL(1, form.image_medium.data)
                        txid_medium = CouponContract.functions.setImageURL(1, form.image_medium.data).transact(
                            {'from':Config.ETH_ACCOUNT, 'gas':gas}
                        )
                    if form.image_large.data != '':
                        gas = CouponContract.estimateGas().setImageURL(2, form.image_large.data)
                        txid = CouponContract.functions.setImageURL(2, form.image_large.data).transact(
                            {'from':Config.ETH_ACCOUNT, 'gas':gas}
                        )
            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/issue.html', form=form)
        else:
            flash_errors(form)
            return render_template('coupon/issue.html', form=form)
    else: # GET
        return render_template('coupon/issue.html', form=form)

# クーポン一覧
@coupon.route('/setting', methods=['GET', 'POST'])
@login_required
def setting():
    logger.info('coupon/setting')


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
            token_exchange_address = to_checksum_address(Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS)
            token_exchange_abi = Config.IBET_COUPON_EXCHANGE_CONTRACT_ABI
            owner = to_checksum_address(Config.ETH_ACCOUNT)
            to_address = form.sendAddress.data
            amount = form.sendAmount.data
            CouponContract = web3.eth.contract(
                address= token.token_address,
                abi = token_abi
            )
            web3.personal.unlockAccount(owner,Config.ETH_ACCOUNT_PASSWORD,1000)
            # 取引所コントラクトへトークン送信
            deposit_gas = CouponContract.estimateGas().transfer(token_exchange_address, amount)
            deposit_txid = CouponContract.functions.transfer(token_exchange_address, amount).\
                        transact({'from':owner, 'gas':deposit_gas})
            tx_receipt = wait_transaction_receipt(deposit_txid)
            if tx_receipt is not None:
                # 取引所コントラクトのtransferで送信相手へ送信
                ExchangeContract = web3.eth.contract(
                    address = token_exchange_address,
                    abi = token_exchange_abi
                )
                transfer_gas = CouponContract.estimateGas().\
                    transfer(token.token_address, to_address, amount)
                transfer_txid = CouponContract.functions.\
                    transfer(token.token_address, to_address, amount).\
                    transact({'from':owner, 'gas':transfer_gas})
            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('token.list'))
        else:
            flash_errors(form)
            return render_template('coupon/transfer.html', form=form)
    else: # GET
        return render_template('coupon/transfer.html', form=form)