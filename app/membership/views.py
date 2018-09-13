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

from . import membership
from .. import db
from ..util import *
from ..models import Role, User, Token, Certification
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
# 発行済債券一覧
####################################################
@membership.route('/list', methods=['GET'])
@login_required
def list():
    logger.info('list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()

    token_list = []
    for row in tokens:
        is_redeemed = False
        is_signed = False

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
            status = TokenContract.functions.status().call()

        token_list.append({
            'name':name,
            'symbol':symbol,
            'created':row.created,
            'tx_hash':row.tx_hash,
            'token_address':row.token_address,
            'status':status
        })

    return render_template('membership/list.html', tokens=token_list)

####################################################
# 債券保有者一覧
####################################################
@membership.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('holders')
    holders, token_name = get_holders_bond(token_address)
    return render_template('membership/holders.html', \
        holders=holders, token_address=token_address, token_name=token_name)

####################################################
# 債券保有者詳細
####################################################
@membership.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('holder')
    personal_info = get_holder(token_address, account_address)
    return render_template('membership/holder.html', personal_info=personal_info, token_address=token_address)

####################################################
# 債券設定
####################################################
@membership.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('token.setting')
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
    interestRate = TokenContract.functions.interestRate().call() * 0.001

    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = json.loads(
        interestPaymentDate_string.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()
    memo = TokenContract.functions.memo().call()
    image_small = TokenContract.functions.getImageURL(0).call()
    image_medium = TokenContract.functions.getImageURL(1).call()
    image_large = TokenContract.functions.getImageURL(2).call()

    form = SettingForm()

    if request.method == 'POST':
        web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
        if form.image_small.data != image_small:
            gas = TokenContract.estimateGas().setImageURL(0, form.image_small.data)
            txid_small = TokenContract.functions.setImageURL(0, form.image_small.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
        if form.image_medium.data != image_medium:
            gas = TokenContract.estimateGas().setImageURL(1, form.image_medium.data)
            txid_medium = TokenContract.functions.setImageURL(1, form.image_medium.data).transact(
                {'from':Config.ETH_ACCOUNT, 'gas':gas}
            )
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
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        if 'interestPaymentDate1' in interestPaymentDate:
            form.interestPaymentDate1.data = interestPaymentDate['interestPaymentDate1']
        if 'interestPaymentDate2' in interestPaymentDate:
            form.interestPaymentDate2.data = interestPaymentDate['interestPaymentDate2']
        if 'interestPaymentDate3' in interestPaymentDate:
            form.interestPaymentDate3.data = interestPaymentDate['interestPaymentDate3']
        if 'interestPaymentDate4' in interestPaymentDate:
            form.interestPaymentDate4.data = interestPaymentDate['interestPaymentDate4']
        if 'interestPaymentDate5' in interestPaymentDate:
            form.interestPaymentDate5.data = interestPaymentDate['interestPaymentDate5']
        if 'interestPaymentDate6' in interestPaymentDate:
            form.interestPaymentDate6.data = interestPaymentDate['interestPaymentDate6']
        if 'interestPaymentDate7' in interestPaymentDate:
            form.interestPaymentDate7.data = interestPaymentDate['interestPaymentDate7']
        if 'interestPaymentDate8' in interestPaymentDate:
            form.interestPaymentDate8.data = interestPaymentDate['interestPaymentDate8']
        if 'interestPaymentDate9' in interestPaymentDate:
            form.interestPaymentDate9.data = interestPaymentDate['interestPaymentDate9']
        if 'interestPaymentDate10' in interestPaymentDate:
            form.interestPaymentDate10.data = interestPaymentDate['interestPaymentDate10']
        if 'interestPaymentDate11' in interestPaymentDate:
            form.interestPaymentDate11.data = interestPaymentDate['interestPaymentDate11']
        if 'interestPaymentDate12' in interestPaymentDate:
            form.interestPaymentDate12.data = interestPaymentDate['interestPaymentDate12']
        form.redemptionDate.data = redemptionDate
        form.redemptionAmount.data = redemptionAmount
        form.returnDate.data = returnDate
        form.returnAmount.data = returnAmount
        form.purpose.data = purpose
        form.memo.data = memo
        form.image_small.data = image_small
        form.image_medium.data = image_medium
        form.image_large.data = image_large
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'membership/setting.html',
            form=form,
            token_address = token_address,
            token_name = name
        )

####################################################
# 認定申請
####################################################
@membership.route('/request_signature/<string:token_address>', methods=['GET','POST'])
@login_required
def request_signature(token_address):
    logger.info('token.request_signature')

    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

    form = RequestSignatureForm()

    if request.method == 'POST':
        if form.validate():

            # 指定した認定者のアドレスが有効なアドレスであるかどうかをチェックする
            if not Web3.isAddress(form.signer.data):
                flash('有効なアドレスではありません。','error')
                return render_template('token/request_signature.html', form=form)

            signer_address = to_checksum_address(form.signer.data)

            # DBに既に情報が登録されている場合はエラーを返す
            if Certification.query.filter(
                Certification.token_address==token_address,
                Certification.signer==signer_address).count() > 0:
                flash('既に情報が登録されています。', 'error')
                return render_template('membership/request_signature.html', form=form)

            # コントラクトに情報を登録する
            try:
                gas = TokenContract.estimateGas().requestSignature(signer_address)
                txid = TokenContract.functions.\
                    requestSignature(signer_address).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            except ValueError:
                flash('処理に失敗しました。', 'error')
                return render_template('membership/request_signature.html', form=form)

            # DBに情報を登録する
            certification = Certification()
            certification.token_address = token_address
            certification.signer = signer_address
            db.session.add(certification)

            flash('認定依頼を受け付けました。', 'success')
            return redirect(url_for('.setting', token_address=token_address))

        else: # Validation Error
            flash_errors(form)
            return render_template('membership/request_signature.html', form=form)

    else: #GET
        form.token_address.data = token_address
        form.signer.data = ''
        return render_template('membership/request_signature.html', form=form)

####################################################
# 債券公開
####################################################
@membership.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('token.release')
    token_address = request.form.get('token_address')

    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract(
        'TokenList', list_contract_address)

    web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

    try:
        gas = ListContract.estimateGas().register(token_address, 'IbetStraightBond')
        register_txid = ListContract.functions.register(token_address, 'IbetStraightBond').\
            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
    except ValueError:
        flash('既に公開されています。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.setting', token_address=token_address))

####################################################
# 債券償還
####################################################
@membership.route('/redeem', methods=['POST'])
@login_required
def redeem():
    logger.info('token.redeem')

    token_address = request.form.get('token_address')

    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= to_checksum_address(token.token_address),
        abi = token_abi
    )

    web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

    try:
        gas = TokenContract.estimateGas().redeem()
        txid = TokenContract.functions.redeem().\
            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
    except ValueError:
        flash('償還処理に失敗しました。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('償還処理中です。完了までに数分程かかることがあります。', 'success')
    return redirect(url_for('.setting', token_address=token_address))

####################################################
# 債券新規発行
####################################################
@membership.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('token.issue')
    form = IssueForm()
    if request.method == 'POST':
        if form.validate():
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                form.details.data,
                form.returnDetails.data,
                form.expirationDate.data,
                form.memo.data,
                form.returnAmount.data,
                form.transferable.data,
                form.status.data
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetMembership')
            contract_address, abi, tx_hash = Contract.deploy_contract(
                'IbetMembership', arguments, Config.ETH_ACCOUNT)

            token = Token()
            token.template_id = Config.TEMPLATE_ID_MEMBERSHIP
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
            return render_template('membership/issue.html', form=form)
    else: # GET
        return render_template('membership/issue.html', form=form)

####################################################
# 保有債券一覧
####################################################
@membership.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()

    # Exchangeコントラクトに接続
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

    position_list = []
    for row in tokens:
        if row.token_address != None:

            # Tokenコントラクトに接続
            TokenContract = web3.eth.contract(
                address=row.token_address,
                abi = json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            )

            owner = to_checksum_address(row.admin_address)

            # 自身が保有している預かりの残高を取得
            balance = TokenContract.functions.balanceOf(owner).call()

            # 拘束中数量を取得する
            commitment = ExchangeContract.functions.\
                commitments(owner, row.token_address).call()

            # 新規注文（NewOrder）のイベント情報を検索する
            event_filter = ExchangeContract.eventFilter(
                'NewOrder', {
                    'filter':{
                        'tokenAddress':row.token_address,
                        'accountAddress':owner
                    },
                    'fromBlock':'earliest'
                }
            )

            order_id = 0
            try:
                entries = event_filter.get_all_entries()
                # キャンセル済みではない注文の注文IDを取得する
                for entry in entries:
                    order_id_tmp = dict(entry['args'])['orderId']
                    canceled = ExchangeContract.functions.orderBook(order_id_tmp).call()[6]
                    if canceled == False:
                        order_id = order_id_tmp
            except:
                continue

            # 拘束数量がゼロよりも大きい場合、募集中のステータスを返す
            on_sale = False
            if balance == 0:
                on_sale = True

            # 残高がゼロよりも大きい場合、または募集中のステータスの場合、リストを返す
            if balance > 0 or on_sale == True:
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
                    'commitment':commitment,
                    'on_sale':on_sale,
                    'order_id':order_id,
                })

    return render_template('token/positions.html', position_list=position_list)

####################################################
# 債券売出
####################################################
@membership.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('sell')
    form = SellForm()

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
    interestRate = TokenContract.functions.interestRate().call() * 0.001

    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = json.loads(
        interestPaymentDate_string.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()
    memo = TokenContract.functions.memo().call()

    owner = to_checksum_address(Config.ETH_ACCOUNT)
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            # PersonalInfo Contract
            personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
            PersonalInfoContract = Contract.get_contract(
                'PersonalInfo', personalinfo_address)

            # WhiteList Contract
            whitelist_address = to_checksum_address(Config.WHITE_LIST_CONTRACT_ADDRESS)
            WhiteListContract = Contract.get_contract(
                'WhiteList', whitelist_address)

            eth_account = to_checksum_address(Config.ETH_ACCOUNT)
            agent_account = to_checksum_address(Config.AGENT_ADDRESS)

            if PersonalInfoContract.functions.isRegistered(eth_account,eth_account).call() == False:
                flash('法人名、所在地の情報が未登録です。', 'error')
                return redirect(url_for('.sell', token_address=token_address))
            elif WhiteListContract.functions.isRegistered(eth_account, agent_account).call() == False:
                flash('金融機関の情報が未登録です。', 'error')
                return redirect(url_for('.sell', token_address=token_address))
            else:
                web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
                token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
                agent_address = to_checksum_address(Config.AGENT_ADDRESS)

                deposit_gas = TokenContract.estimateGas().transfer(token_exchange_address, balance)
                deposit_txid = TokenContract.functions.transfer(token_exchange_address, balance).\
                    transact({'from':owner, 'gas':deposit_gas})

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

                ExchangeContract = Contract.get_contract(
                    'IbetStraightBondExchange', token_exchange_address)

                sell_gas = ExchangeContract.estimateGas().\
                    createOrder(token_address, balance, form.sellPrice.data, False, agent_address)
                sell_txid = ExchangeContract.functions.\
                    createOrder(token_address, balance, form.sellPrice.data, False, agent_address).\
                    transact({'from':owner, 'gas':sell_gas})

                flash('新規募集を受け付けました。募集開始までに数分程かかることがあります。', 'success')
                return redirect(url_for('.positions'))

        else:
            flash_errors(form)
            return redirect(url_for('.sell', token_address=token_address))

    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        if 'interestPaymentDate1' in interestPaymentDate:
            form.interestPaymentDate1.data = interestPaymentDate['interestPaymentDate1']
        else:
            form.interestPaymentDate1.data = ""
        if 'interestPaymentDate2' in interestPaymentDate:
            form.interestPaymentDate2.data = interestPaymentDate['interestPaymentDate2']
        else:
            form.interestPaymentDate2.data = ""
        if 'interestPaymentDate3' in interestPaymentDate:
            form.interestPaymentDate3.data = interestPaymentDate['interestPaymentDate3']
        else:
            form.interestPaymentDate3.data = ""
        if 'interestPaymentDate4' in interestPaymentDate:
            form.interestPaymentDate4.data = interestPaymentDate['interestPaymentDate4']
        else:
            form.interestPaymentDate4.data = ""
        if 'interestPaymentDate5' in interestPaymentDate:
            form.interestPaymentDate5.data = interestPaymentDate['interestPaymentDate5']
        else:
            form.interestPaymentDate5.data = ""
        if 'interestPaymentDate6' in interestPaymentDate:
            form.interestPaymentDate6.data = interestPaymentDate['interestPaymentDate6']
        else:
            form.interestPaymentDate6.data = ""
        if 'interestPaymentDate7' in interestPaymentDate:
            form.interestPaymentDate7.data = interestPaymentDate['interestPaymentDate7']
        else:
            form.interestPaymentDate7.data = ""
        if 'interestPaymentDate8' in interestPaymentDate:
            form.interestPaymentDate8.data = interestPaymentDate['interestPaymentDate8']
        else:
            form.interestPaymentDate8.data = ""
        if 'interestPaymentDate9' in interestPaymentDate:
            form.interestPaymentDate9.data = interestPaymentDate['interestPaymentDate9']
        else:
            form.interestPaymentDate9.data = ""
        if 'interestPaymentDate10' in interestPaymentDate:
            form.interestPaymentDate10.data = interestPaymentDate['interestPaymentDate10']
        else:
            form.interestPaymentDate10.data = ""
        if 'interestPaymentDate11' in interestPaymentDate:
            form.interestPaymentDate11.data = interestPaymentDate['interestPaymentDate11']
        else:
            form.interestPaymentDate11.data = ""
        if 'interestPaymentDate12' in interestPaymentDate:
            form.interestPaymentDate12.data = interestPaymentDate['interestPaymentDate12']
        else:
            form.interestPaymentDate12.data = ""
        form.redemptionDate.data = redemptionDate
        form.redemptionAmount.data = redemptionAmount
        form.returnDate.data = returnDate
        form.returnAmount.data = returnAmount
        form.purpose.data = purpose
        form.memo.data = memo
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template(
            'token/sell.html',
            token_address = token_address,
            token_name = name,
            form = form
        )

####################################################
# 債券売出停止
####################################################
@membership.route('/cancel_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def cancel_order(order_id):
    logger.info('cancel_order')
    form = CancelOrderForm()

    # Exchangeコントラクトに接続
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

    # 注文情報を取得する
    orderBook = ExchangeContract.functions.orderBook(order_id).call()
    token_address = orderBook[1]
    amount = orderBook[2]
    price = orderBook[3]

    # トークンのABIを取得する
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # トークンコントラクトに接続する
    TokenContract = web3.eth.contract(
        address= to_checksum_address(token_address),
        abi = token_abi
    )

    # トークンの商品名、略称、総発行量を取得する
    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    faceValue = TokenContract.functions.faceValue().call()

    if request.method == 'POST':
        if form.validate():
            web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
            gas = ExchangeContract.estimateGas().cancelOrder(order_id)
            txid = ExchangeContract.functions.cancelOrder(order_id).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            flash('募集停止処理を受け付けました。停止されるまでに数分程かかることがあります。', 'success')
            return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return redirect(url_for('.cancel_order', order_id=order_id))
    else: # GET
        form.order_id.data = order_id
        form.token_address.data = token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.amount.data = amount
        form.faceValue.data = faceValue
        form.price.data = price
        return render_template('token/cancel_order.html', form=form)

####################################################
# 権限エラー
####################################################
@membership.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')

