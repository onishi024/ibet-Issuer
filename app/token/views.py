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

from . import token
from .. import db
from ..models import Role, User, Token, Certification
from .forms import IssueTokenForm, TokenSettingForm, SellTokenForm, CancelOrderForm, RequestSignatureForm
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
# 発行済債券一覧
####################################################
@token.route('/tokenlist', methods=['GET'])
@login_required
def list():
    logger.info('list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.all()

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

            # 償還（Redeem）のイベント情報を検索する
            event_filter_redeem = TokenContract.eventFilter(
                'Redeem', {
                    'filter':{},
                    'fromBlock':'earliest'
                }
            )
            try:
                entries_redeem = event_filter_redeem.get_all_entries()
            except:
                entries_redeem = []

            if len(entries_redeem) > 0:
                is_redeemed = True

            # 第三者認定（Sign）のイベント情報を検索する
            event_filter_sign = TokenContract.eventFilter(
                'Sign', {
                    'filter':{},
                    'fromBlock':'earliest'
                }
            )
            try:
                entries_sign = event_filter_sign.get_all_entries()
            except:
                entries_sign = []

            for entry in entries_sign:
                if TokenContract.functions.\
                    signatures(to_checksum_address(entry['args']['signer'])).call() == 2:
                    is_signed = True

        token_list.append({
            'name':name,
            'symbol':symbol,
            'created':row.created,
            'tx_hash':row.tx_hash,
            'token_address':row.token_address,
            'is_redeemed':is_redeemed,
            'is_signed':is_signed
        })

    return render_template('token/list.html', tokens=token_list)

####################################################
# 債券保有者一覧
####################################################
@token.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('holders')

    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    # Token Contract
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # Exchange Contract
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    token_exchange_abi = Config.IBET_SB_EXCHANGE_CONTRACT_ABI
    ExchangeContract = web3.eth.contract(
        address = token_exchange_address,
        abi = token_exchange_abi
    )

    # PersonalInfo Contract
    personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    personalinfo_abi = Config.PERSONAL_INFO_CONTRACT_ABI
    PersonalInfoContract = web3.eth.contract(
        address = personalinfo_address,
        abi = personalinfo_abi
    )

    # 残高を保有している可能性のあるアドレスを抽出する
    holders_temp = []
    holders_temp.append(TokenContract.functions.owner().call())

    event_filter = TokenContract.eventFilter(
        'Transfer', {
            'filter':{},
            'fromBlock':'earliest'
        }
    )
    entries = event_filter.get_all_entries()
    for entry in entries:
        holders_temp.append(entry['args']['to'])

    # 口座リストをユニークにする
    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    token_owner = TokenContract.functions.owner().call()
    token_name = TokenContract.functions.name().call()

    # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        commitment = ExchangeContract.functions.\
            commitments(account_address,token_address).call()
        if balance > 0 or commitment > 0:
            encrypted_info = PersonalInfoContract.functions.\
                personal_info(account_address, token_owner).call()[2]
            if encrypted_info == '' or cipher == None:
                name = ''
            else:
                ciphertext = base64.decodestring(encrypted_info.encode('utf-8'))
                try:
                    message = cipher.decrypt(ciphertext)
                    personal_info_json = json.loads(message)
                    name = personal_info_json['name']
                except:
                    name = ''

            holder = {
                'account_address':account_address,
                'name':name,
                'balance':balance,
                'commitment':commitment,
            }
            holders.append(holder)

    return render_template('token/holders.html', \
        holders=holders, token_address=token_address, token_name=token_name)

####################################################
# 債券保有者詳細
####################################################
@token.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('holder')

    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        pass

    # Token Contract
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # PersonalInfo Contract
    personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    personalinfo_abi = Config.PERSONAL_INFO_CONTRACT_ABI
    PersonalInfoContract = web3.eth.contract(
        address = personalinfo_address,
        abi = personalinfo_abi
    )

    personal_info = {
        "name":"--",
        "address":{
            "postal_code":"--",
            "prefecture":"--",
            "city":"--",
            "address1":"--",
            "address2":"--"
        },
        "bank_account":{
            "bank_name": "--",
            "branch_office": "--",
            "account_type": "--",
            "account_number": "--",
            "account_holder": "--"
        }
    }

    token_owner = TokenContract.functions.owner().call()

    encrypted_info = PersonalInfoContract.functions.\
        personal_info(account_address, token_owner).call()[2]

    if encrypted_info == '' or cipher == None:
        pass
    else:
        ciphertext = base64.decodestring(encrypted_info.encode('utf-8'))
        try:
            message = cipher.decrypt(ciphertext)
            personal_info = json.loads(message)
        except:
            pass

    return render_template('token/holder.html', personal_info=personal_info, token_address=token_address)

####################################################
# 債券設定
####################################################
@token.route('/setting/<string:token_address>', methods=['GET', 'POST'])
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
    image_small = TokenContract.functions.getImageURL(0).call()
    image_medium = TokenContract.functions.getImageURL(1).call()
    image_large = TokenContract.functions.getImageURL(2).call()

    form = TokenSettingForm()

    if request.method == 'POST':
        web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)
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
        form.image_small.data = image_small
        form.image_medium.data = image_medium
        form.image_large.data = image_large
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template('token/setting.html', form=form, token_address=token_address)

####################################################
# 認定申請
####################################################
@token.route('/request_signature/<string:token_address>', methods=['GET','POST'])
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
                return render_template('token/request_signature.html', form=form)

            # コントラクトに情報を登録する
            try:
                gas = TokenContract.estimateGas().requestSignature(signer_address)
                txid = TokenContract.functions.\
                    requestSignature(signer_address).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            except ValueError:
                flash('処理に失敗しました。', 'error')
                return render_template('token/request_signature.html', form=form)

            # DBに情報を登録する
            certification = Certification()
            certification.token_address = token_address
            certification.signer = signer_address
            db.session.add(certification)

            flash('認定依頼を受け付けました。', 'success')
            return redirect(url_for('.setting', token_address=token_address))

        else: # Validation Error
            flash_errors(form)
            return render_template('token/request_signature.html', form=form)

    else: #GET
        form.token_address.data = token_address
        form.signer.data = ''
        return render_template('token/request_signature.html', form=form)

####################################################
# 債券公開
####################################################
@token.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('token.release')
    token_address = request.form.get('token_address')

    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    list_contract_abi = json.loads(Config.TOKEN_LIST_CONTRACT_ABI)

    web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,1000)

    ListContract = web3.eth.contract(
        address = to_checksum_address(list_contract_address),
        abi = list_contract_abi
    )

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
@token.route('/redeem', methods=['POST'])
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
@token.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('token.issue')
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

            interestPaymentDate = {
                'interestPaymentDate1': form.interestPaymentDate1.data,
                'interestPaymentDate2': form.interestPaymentDate2.data,
                'interestPaymentDate3': form.interestPaymentDate3.data,
                'interestPaymentDate4': form.interestPaymentDate4.data,
                'interestPaymentDate5': form.interestPaymentDate5.data,
                'interestPaymentDate6': form.interestPaymentDate6.data,
                'interestPaymentDate7': form.interestPaymentDate7.data,
                'interestPaymentDate8': form.interestPaymentDate8.data,
                'interestPaymentDate9': form.interestPaymentDate9.data,
                'interestPaymentDate10': form.interestPaymentDate10.data,
                'interestPaymentDate11': form.interestPaymentDate11.data,
                'interestPaymentDate12': form.interestPaymentDate12.data
            }

            interestPaymentDate_string = json.dumps(interestPaymentDate)

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                form.faceValue.data,
                int(form.interestRate.data * 1000),
                interestPaymentDate_string,
                form.redemptionDate.data,
                form.redemptionAmount.data,
                form.returnDate.data,
                form.returnAmount.data,
                form.purpose.data
            ]

            tx_hash = TokenContract.deploy(
                transaction={'from':Config.ETH_ACCOUNT, 'gas':4000000},
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

####################################################
# 保有債券一覧
####################################################
@token.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.all()

    # Exchangeコントラクトに接続
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    token_exchange_abi = Config.IBET_SB_EXCHANGE_CONTRACT_ABI
    ExchangeContract = web3.eth.contract(
        address = token_exchange_address,
        abi = token_exchange_abi
    )

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
    interestRate = TokenContract.functions.interestRate().call() * 0.001

    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = json.loads(
        interestPaymentDate_string.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()

    owner = to_checksum_address(Config.ETH_ACCOUNT)
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            # PersonalInfo Contract
            personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
            personalinfo_abi = Config.PERSONAL_INFO_CONTRACT_ABI
            PersonalInfoContract = web3.eth.contract(
                address = personalinfo_address,
                abi = personalinfo_abi
            )

            # WhiteList Contract
            whitelist_address = to_checksum_address(Config.WHITE_LIST_CONTRACT_ADDRESS)
            whitelist_abi = Config.WHITE_LIST_CONTRACT_ABI
            WhiteListContract = web3.eth.contract(
                address = whitelist_address,
                abi = whitelist_abi
            )

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
                token_exchange_abi = Config.IBET_SB_EXCHANGE_CONTRACT_ABI
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

                ExchangeContract = web3.eth.contract(
                    address = token_exchange_address,
                    abi = token_exchange_abi
                )
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
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template('token/sell.html', form=form)

####################################################
# 債券売出停止
####################################################
@token.route('/cancel_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def cancel_order(order_id):
    logger.info('cancel_order')
    form = CancelOrderForm()

    # Exchangeコントラクトに接続
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    token_exchange_abi = Config.IBET_SB_EXCHANGE_CONTRACT_ABI
    ExchangeContract = web3.eth.contract(
        address = token_exchange_address,
        abi = token_exchange_abi
    )

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
