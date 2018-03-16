# -*- coding:utf-8 -*-
import secrets
import datetime
import json
import time
from base64 import b64encode

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

from . import token
from .. import db
from ..models import Role, User, Token
from .forms import IssueTokenForm, TokenSettingForm, SellTokenForm
from ..decorators import admin_required
from config import Config

from logging import getLogger
logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))

#+++++++++++++++++++++++++++++++
# Utils
#+++++++++++++++++++++++++++++++
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')

#+++++++++++++++++++++++++++++++
# Views
#+++++++++++++++++++++++++++++++
@token.route('/tokenlist', methods=['GET'])
@login_required
def list():
    logger.info('list')
    tokens = Token.query.all()
    token_list = []
    for row in tokens:
        if row.token_address != None:
            MyContract = web3.eth.contract(
                address=row.token_address,
                abi = json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            )
            name = MyContract.functions.name().call()
            symbol = MyContract.functions.symbol().call()
        else:
            name = '<処理中>'
            symbol = '<処理中>'
        token_list.append({
            'name':name,
            'symbol':symbol,
            'created':row.created,
            'tx_hash':row.tx_hash,
            'token_address':row.token_address
        })

    return render_template('token/list.html', tokens=token_list)


@token.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('token.token_address')
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    faceValue = TokenContract.functions.faceValue().call()
    interestRate = TokenContract.functions.interestRate().call()
    interestPaymentDate1 = TokenContract.functions.interestPaymentDate1().call()
    interestPaymentDate2 = TokenContract.functions.interestPaymentDate2().call()
    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()

    form = TokenSettingForm()
    if request.method == 'POST':
        pass
    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        form.interestPaymentDate1.data = interestPaymentDate1
        form.interestPaymentDate2.data = interestPaymentDate2
        form.redemptionDate.data = redemptionDate
        form.redemptionAmount.data = redemptionAmount
        form.returnDate.data = returnDate
        form.returnAmount.data = returnAmount
        form.purpose.data = purpose
        form.image_small.data = None
        form.image_medium.data = None
        form.image_large.data = None
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template('token/setting.html', form=form)

@token.route('/release', methods=['POST'])
@login_required
def release():
    token_address = request.form.get('token_address')

    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    list_contract_abi = json.loads(Config.TOKEN_LIST_CONTRACT_ABI)

    web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

    ListContract = web3.eth.contract(
        address = list_contract_address,
        abi = list_contract_abi
    )

    register_txid = ListContract.functions.register(token_address, 'IbetStraightBond').transact(
        {'from':web3.eth.accounts[0], 'gas':3000000}
    )

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.setting', token_address=token_address))


@token.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('issue')
    form = IssueTokenForm()
    if request.method == 'POST':
        if form.validate():
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

            abi = json.loads(Config.IBET_SB_CONTRACT_ABI)
            bytecode = Config.IBET_SB_CONTRACT_BYTECODE
            bytecode_runtime = Config.IBET_SB_CONTRACT_BYTECODE_RUNTIME

            TokenContract = web3.eth.contract(
                abi = abi,
                bytecode = bytecode,
                bytecode_runtime = bytecode_runtime,
            )

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                form.faceValue.data,
                form.interestRate.data,
                form.interestPaymentDate1.data,
                form.interestPaymentDate2.data,
                form.redemptionDate.data,
                form.redemptionAmount.data,
                form.returnDate.data,
                form.returnAmount.data,
                form.purpose.data
            ]

            tx_hash = TokenContract.deploy(
                transaction={'from':web3.eth.accounts[0], 'gas':5000000},
                args=arguments
            ).hex()

            token = Token()
            token.template_id = 1
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('token/issue.html', form=form)
    else: # GET
        return render_template('token/issue.html', form=form)


@token.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('positions')
    tokens = Token.query.all()
    position_list = []
    for row in tokens:
        if row.token_address != None:
            TokenContract = web3.eth.contract(
                address=row.token_address,
                abi = json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            )

            owner = to_checksum_address(row.admin_address)
            balance = TokenContract.functions.balanceOf(owner).call()

            if balance > 0 :
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                totalSupply = TokenContract.functions.totalSupply().call()
                position_list.append({
                    'token_address':row.token_address,
                    'name':name,
                    'symbol':symbol,
                    'totalSupply':totalSupply,
                    'balance':balance,
                    'created':row.created,
                })

    return render_template('token/positions.html', position_list=position_list)


@token.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('sell')
    form = SellTokenForm()

    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    faceValue = TokenContract.functions.faceValue().call()
    interestRate = TokenContract.functions.interestRate().call()
    interestPaymentDate1 = TokenContract.functions.interestPaymentDate1().call()
    interestPaymentDate2 = TokenContract.functions.interestPaymentDate2().call()
    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()

    owner = to_checksum_address(web3.eth.accounts[0])
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

            token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
            token_exchange_abi = Config.IBET_SB_EXCHANGE_CONTRACT_ABI
            agent_address = to_checksum_address(Config.AGENT_ADDRESS)

            deposit_gas = TokenContract.estimateGas().transfer(token_exchange_address, balance)

            deposit_txid = TokenContract.functions.transfer(token_exchange_address, balance).transact(
                {'from':owner, 'gas':deposit_gas}
            )

            count = 0
            deposit_tx_receipt = None
            while True:
                try:
                    deposit_tx_receipt = web3.eth.getTransactionReceipt(deposit_txid)
                except:
                    time.sleep(1)

                count += 1
                if deposit_tx_receipt is not None or count > 30:
                    break

            ExchangeContract = web3.eth.contract(
                address = token_exchange_address,
                abi = token_exchange_abi
            )

            sell_gas = ExchangeContract.estimateGas().createOrder(token_address, balance, form.sellPrice.data, False, agent_address)

            sell_txid = ExchangeContract.functions.createOrder(token_address, balance, form.sellPrice.data, False, agent_address).transact(
                {'from':owner, 'gas':sell_gas}
            )

            flash('新規募集を受け付けました。募集開始までに数分程かかることがあります。', 'success')
            return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return render_template('token/sell.html', form=form)
    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        form.interestPaymentDate1.data = interestPaymentDate1
        form.interestPaymentDate2.data = interestPaymentDate2
        form.redemptionDate.data = redemptionDate
        form.redemptionAmount.data = redemptionAmount
        form.returnDate.data = returnDate
        form.returnAmount.data = returnAmount
        form.purpose.data = purpose
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template('token/sell.html', form=form)


@token.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')

#+++++++++++++++++++++++++++++++
# Custom Filter
#+++++++++++++++++++++++++++++++
@token.app_template_filter()
def format_date(date): # date = datetime object.
    if date:
        if isinstance(date, datetime.datetime):
            return date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(date, datetime.date):
            return date.strftime('%Y/%m/%d')
    return ''

@token.app_template_filter()
def img_convert(icon):
    if icon:
        img = b64encode(icon)
        return img.decode('utf8')
    return None
