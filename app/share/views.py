# -*- coding:utf-8 -*-
import json
import base64
import re
from datetime import datetime, date
import io
import time

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from flask import request, redirect, url_for, flash, make_response, render_template, abort, jsonify
from flask_login import login_required
from sqlalchemy import func, desc

from app import db
from app.util import eth_unlock_account, get_holder
from app.models import Token, Certification, Order, Agreement, AgreementStatus, Transfer, AddressType, ApplyFor
from app.contracts import Contract
from config import Config
from . import share
from .forms import IssueForm

from web3 import Web3
from eth_utils import to_checksum_address
from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

from logging import getLogger

logger = getLogger('api')


####################################################
# 共通処理
####################################################

# 共通処理：エラー表示
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


####################################################
# [株式]新規発行
####################################################
@share.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('share/issue')
    form = IssueForm()

    if request.method == 'POST':
        if form.validate():
            # EOAアンロック
            eth_unlock_account()

            # トークン発行（トークンコントラクトのデプロイ）
            # bool型に変換
            bool_transferable = form.transferable.data != 'False'

            arguments = [
                form.name.data,
                form.symbol.data,
                to_checksum_address(form.tradableExchange.data),
                to_checksum_address(form.personalInfoAddress.data),
                form.issuePrice.data,
                form.totalSupply.data,
                form.dividends.data,
                form.dividendRecordDate.data,
                form.dividendPaymentDate.data,
                form.cansellationDate.data,
                form.contact_information.data,
                form.privacy_policy.data,
                form.memo.data,
                bool_transferable
            ]

            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetShare')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract('IbetShare', arguments, Config.ETH_ACCOUNT)

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_SHARE
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            # 関連URLの登録処理
            if form.referenceUrls_1.data != '' or form.referenceUrls_2.data != '' or form.referenceUrls_3.data != '':
                # トークンのデプロイ完了まで待つ
                tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
                # トークンが正常にデプロイされた後に画像URLの登録処理を実行する
                if tx_receipt is not None:
                    TokenContract = web3.eth.contract(
                        address=tx_receipt['contractAddress'],
                        abi=abi
                    )
                    if form.referenceUrls_1.data != '':
                        gas = TokenContract.estimateGas().setReferenceUrls(0, form.referenceUrls_1.data)
                        TokenContract.functions.setReferenceUrls(0, form.referenceUrls_1.data).transact(
                            {'from': Config.ETH_ACCOUNT, 'gas': gas}
                        )
                    if form.referenceUrls_2.data != '':
                        gas = TokenContract.estimateGas().setReferenceUrls(1, form.referenceUrls_2.data)
                        TokenContract.functions.setReferenceUrls(1, form.referenceUrls_2.data).transact(
                            {'from': Config.ETH_ACCOUNT, 'gas': gas}
                        )
                    if form.referenceUrls_3.data != '':
                        gas = TokenContract.estimateGas().setReferenceUrls(2, form.referenceUrls_3.data)
                        TokenContract.functions.setReferenceUrls(2, form.referenceUrls_2.data).transact(
                            {'from': Config.ETH_ACCOUNT, 'gas': gas}
                        )

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('share/issue.html', form=form, form_description=form.description)
    else:  # GET
        form.tradableExchange.data = Config.IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS
        form.personalInfoAddress.data = Config.PERSONAL_INFO_CONTRACT_ADDRESS
        return render_template('share/issue.html', form=form, form_description=form.description)


####################################################
# [株式]発行済一覧
####################################################
@share.route('/list', methods=['GET'])
@login_required
def list():
    # TODO: 実装する。tempateでエラーが発生しないようにするためにダミーで作成している。
    logger.info('share/list')
    form = IssueForm()
    form.tradableExchange.data = Config.IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS
    form.personalInfoAddress.data = Config.PERSONAL_INFO_CONTRACT_ADDRESS
    return render_template('share/issue.html', form=form, form_description=form.description)


####################################################
# 権限エラー
####################################################
@share.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')


####################################################
# Custom Filter
####################################################
@share.app_template_filter()
def format_date(_date):  # _date = datetime object.
    if _date:
        if isinstance(_date, datetime):
            return _date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(_date, date):
            return _date.strftime('%Y/%m/%d')
    return ''
