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
from ..util import *
from .forms import *
from ..decorators import admin_required
from config import Config
from app.contracts import Contract

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
# クーポン一覧
####################################################
@coupon.route('/list', methods=['GET', 'POST'])
@login_required
def list():
    logger.info('coupon/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()

    token_list = []
    for row in tokens:
        # トークンがデプロイ済みの場合、トークン情報を取得する
        if row.token_address == None:
            name = '<処理中>'
            symbol = '<処理中>'
            is_valid = '<処理中>'
            token_address = None
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
            token_address = row.token_address
        token_list.append({
            'name':name,
            'symbol':symbol,
            'is_valid':is_valid,
            'created':row.created,
            'token_address':token_address
        })

    return render_template('coupon/list.html', tokens=token_list)

####################################################
# クーポン発行
####################################################
@coupon.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('coupon/issue')
    form = IssueCouponForm()
    if request.method == 'POST':
        if form.validate():
            ####### トークン発行処理 #######
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                form.details.data,
                form.memo.data,
                form.expirationDate.data,
                form.transferable.data
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetCoupon')
            contract_address, abi, tx_hash = Contract.deploy_contract(
                'IbetCoupon', arguments, Config.ETH_ACCOUNT)

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
                    TokenContract = web3.eth.contract(
                        address= tx_receipt['contractAddress'],
                        abi = abi
                    )
                    if form.image_small.data != '':
                        gas = TokenContract.estimateGas().setImageURL(0, form.image_small.data)
                        txid_small = TokenContract.functions.setImageURL(0, form.image_small.data).transact(
                            {'from':Config.ETH_ACCOUNT, 'gas':gas}
                        )
                    if form.image_medium.data != '':
                        gas = TokenContract.estimateGas().setImageURL(1, form.image_medium.data)
                        txid_medium = TokenContract.functions.setImageURL(1, form.image_medium.data).transact(
                            {'from':Config.ETH_ACCOUNT, 'gas':gas}
                        )
                    if form.image_large.data != '':
                        gas = TokenContract.estimateGas().setImageURL(2, form.image_large.data)
                        txid = TokenContract.functions.setImageURL(2, form.image_large.data).transact(
                            {'from':Config.ETH_ACCOUNT, 'gas':gas}
                        )
            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('coupon/issue.html', form=form)
    else: # GET
        return render_template('coupon/issue.html', form=form)

# 追加発行
@coupon.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info('coupon/add_supply')

    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    owner = to_checksum_address(Config.ETH_ACCOUNT)
    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )
    form = AddSupplyForm()
    form.token_address.data = token.token_address
    form.name.data = TokenContract.functions.name().call()
    form.totalSupply.data = TokenContract.functions.totalSupply().call()
    if request.method == 'POST':
        if form.validate():
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

            gas = TokenContract.estimateGas().issue(form.addSupply.data)
            tx = TokenContract.functions.issue(form.addSupply.data).\
                        transact({'from':owner, 'gas':gas})
            wait_transaction_receipt(tx)

            flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('coupon/add_supply.html', form=form)
    else: # GET
        return render_template('coupon/add_supply.html', form=form)

####################################################
# クーポン編集
####################################################
@coupon.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('coupon/setting')
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    details = TokenContract.functions.details().call()
    memo = TokenContract.functions.memo().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    isValid = TokenContract.functions.isValid().call()
    transferable = TokenContract.functions.transferable().call()
    image_small = TokenContract.functions.getImageURL(0).call()
    image_medium = TokenContract.functions.getImageURL(1).call()
    image_large = TokenContract.functions.getImageURL(2).call()

    form = IssueCouponForm()

    if request.method == 'POST':
        web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
        # 詳細
        if form.details.data != details:
            gas = TokenContract.estimateGas().updateDetails(form.details.data)
            txid = TokenContract.functions.updateDetails(form.details.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
        # memo
        if form.memo.data != memo:
            gas = TokenContract.estimateGas().updateMemo(form.memo.data)
            txid = TokenContract.functions.updateMemo(form.memo.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
        # 画像 小
        if form.image_small.data != image_small:
            gas = TokenContract.estimateGas().setImageURL(0, form.image_small.data)
            txid_small = TokenContract.functions.setImageURL(0, form.image_small.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
        # 画像 中
        if form.image_medium.data != image_medium:
            gas = TokenContract.estimateGas().setImageURL(1, form.image_medium.data)
            txid_medium = TokenContract.functions.setImageURL(1, form.image_medium.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
        # 画像 大
        if form.image_large.data != image_large:
            gas = TokenContract.estimateGas().setImageURL(2, form.image_large.data)
            txid = TokenContract.functions.setImageURL(2, form.image_large.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
        flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
        return redirect(url_for('.list'))
    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.details.data = details
        form.isValid.data = isValid
        form.expirationDate.data = expirationDate
        form.transferable.data = transferable
        form.memo.data = memo
        form.image_small.data = image_small
        form.image_medium.data = image_medium
        form.image_large.data = image_large
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template('coupon/setting.html', form=form, token_address=token_address)

####################################################
# クーポン割当
####################################################
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
            owner = to_checksum_address(Config.ETH_ACCOUNT)
            to_address = to_checksum_address(form.sendAddress.data)
            amount = form.sendAmount.data
            TokenContract = web3.eth.contract(
                address= token.token_address,
                abi = token_abi
            )
            web3.personal.unlockAccount(owner,Config.ETH_ACCOUNT_PASSWORD,1000)
            # 取引所コントラクトへトークン送信
            deposit_gas = TokenContract.estimateGas().allocate(token_exchange_address, amount)
            deposit_txid = TokenContract.functions.allocate(token_exchange_address, amount).\
                        transact({'from':owner, 'gas':deposit_gas})
            tx_receipt = wait_transaction_receipt(deposit_txid)
            if tx_receipt is not None:
                # 取引所コントラクトのtransferで送信相手へ送信
                ExchangeContract = Contract.get_contract(
                    'IbetCouponExchange', token_exchange_address)
                transfer_gas = ExchangeContract.estimateGas().\
                    transfer(token.token_address, to_address, amount)
                transfer_txid = ExchangeContract.functions.\
                    transfer(token.token_address, to_address, amount).\
                    transact({'from':owner, 'gas':transfer_gas})
            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/transfer.html', form=form)
        else:
            flash_errors(form)
            return render_template('coupon/transfer.html', form=form)
    else: # GET
        return render_template('coupon/transfer.html', form=form)


####################################################
# coupon保有者一覧
####################################################
@coupon.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('coupon/holders')
    holders, token_name = get_holders_coupon(token_address)
    return render_template('coupon/holders.html', \
        holders=holders, token_address=token_address, token_name=token_name)

####################################################
# coupon保有者詳細
####################################################
@coupon.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('coupon/holder')
    personal_info = get_holder(token_address, account_address)
    return render_template('coupon/holder.html', personal_info=personal_info, token_address=token_address)


####################################################
# 有効化/無効化
####################################################
@coupon.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info('coupon/valid')
    coupon_valid(request.form.get('token_address'), True)
    return redirect(url_for('.list'))

@coupon.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info('coupon/invalid')
    coupon_valid(request.form.get('token_address'), False)
    return redirect(url_for('.list'))


def coupon_valid(token_address, isvalid):
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    owner = to_checksum_address(Config.ETH_ACCOUNT)
    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )
    web3.personal.unlockAccount(owner,Config.ETH_ACCOUNT_PASSWORD,1000)

    gas = TokenContract.estimateGas().updateStatus(isvalid)
    tx = TokenContract.functions.updateStatus(isvalid).\
                transact({'from':owner, 'gas':gas})

    wait_transaction_receipt(tx)

    flash('処理を受け付けました。完了までに数分程かかることがあります。', 'success')
