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
from flask import abort
from flask_login import login_required
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

# クーポントークンの保有者一覧、token_nameを返す
def get_holders_coupon(token_address):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    # Coupon Token Contract
    # Note: token_addressに対して、Couponトークンのものであるかはチェックしていない。
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # PersonalInfo Contract
    personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personalinfo_address)

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

    # 残高（balance）、または使用済（used）が存在する情報を抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        used = TokenContract.functions.usedOf(account_address).call()
        if balance > 0 or used > 0:
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
                'used': used
            }
            holders.append(holder)

    return holders, token_name

# クーポントークンの利用履歴を返す
def get_usege_history_coupon(token_address):
    # Coupon Token Contract
    # Note: token_addressに対して、Couponトークンのものであるかはチェックしていない。
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').\
        replace('True', 'true').replace('False', 'false'))
    CouponContract = web3.eth.contract(
        address= token_address, abi = token_abi)

    # クーポン名を取得
    token_name = CouponContract.functions.name().call()

    # クーポントークンの消費イベント（Consume）を検索
    try:
        event_filter = CouponContract.eventFilter(
            'Consume', {
                'filter':{},
                'fromBlock':'earliest'
            }
        )
        entries = event_filter.get_all_entries()
        web3.eth.uninstallFilter(event_filter.filter_id)
    except:
        entries = []

    usage_list = []
    for entry in entries:
        usage = {
            'block_timestamp': datetime.fromtimestamp(
                web3.eth.getBlock(entry['blockNumber'])['timestamp'],JST).\
                strftime("%Y/%m/%d %H:%M:%S"),
            'consumer': entry['args']['consumer'],
            'value': entry['args']['value']
        }
        usage_list.append(usage)

    return token_address, token_name, usage_list

####################################################
# [クーポン]一覧
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
            'tx_hash':row.tx_hash,
            'created':row.created,
            'token_address':row.token_address
        })

    return render_template('coupon/list.html', tokens=token_list)

####################################################
# [クーポン]公開
####################################################
@coupon.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('coupon/release')
    eth_unlock_account()

    token_address = request.form.get('token_address')
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.\
        get_contract('TokenList', list_contract_address)

    try:
        gas = ListContract.estimateGas().\
            register(token_address, 'IbetCoupon')
        register_txid = ListContract.functions.\
            register(token_address, 'IbetCoupon').\
            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
    except ValueError:
        flash('既に公開されています。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.list'))

####################################################
# [クーポン]新規発行
####################################################
@coupon.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('coupon/issue')
    form = IssueCouponForm()
    if request.method == 'POST':
        if form.validate():
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。','error')
                return render_template('coupon/issue.html', form=form)

            eth_unlock_account()

            ####### トークン発行処理 #######
            tmpVal = True
            if form.transferable.data == 'False':
                tmpVal = False

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                to_checksum_address(form.tradableExchange.data),
                form.details.data,
                form.memo.data,
                form.expirationDate.data,
                tmpVal
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetCoupon')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract('IbetCoupon', arguments, Config.ETH_ACCOUNT)

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
                        gas = TokenContract.estimateGas().\
                            setImageURL(0, form.image_small.data)
                        txid_small = TokenContract.functions.\
                            setImageURL(0, form.image_small.data).\
                            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
                    if form.image_medium.data != '':
                        gas = TokenContract.estimateGas().\
                            setImageURL(1, form.image_medium.data)
                        txid_medium = TokenContract.functions.\
                            setImageURL(1, form.image_medium.data).\
                            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
                    if form.image_large.data != '':
                        gas = TokenContract.estimateGas().\
                            setImageURL(2, form.image_large.data)
                        txid = TokenContract.functions.\
                            setImageURL(2, form.image_large.data).\
                            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

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
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )
    form = AddSupplyForm()
    form.token_address.data = token.token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.totalSupply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            gas = TokenContract.estimateGas().issue(form.addSupply.data)
            TokenContract.functions.issue(form.addSupply.data).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template(
                'coupon/add_supply.html',
                form = form,
                token_address = token_address,
                token_name = name
            )
    else: # GET
        return render_template(
            'coupon/add_supply.html',
            form = form,
            token_address = token_address,
            token_name = name
        )

####################################################
# [クーポン]設定内容修正
####################################################
@coupon.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('coupon/setting')
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

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
    transferable = str(TokenContract.functions.transferable().call())
    image_small = TokenContract.functions.getImageURL(0).call()
    image_medium = TokenContract.functions.getImageURL(1).call()
    image_large = TokenContract.functions.getImageURL(2).call()
    tradableExchange = TokenContract.functions.tradableExchange().call()

    # TokenListへの登録有無
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.\
        get_contract('TokenList', list_contract_address)
    token_struct = ListContract.functions.\
        getTokenByAddress(token_address).call()

    isReleased = False
    if token_struct[0] == token_address:
        isReleased = True

    form = SettingCouponForm()
    if request.method == 'POST':
        if form.validate(): # Validationチェック
            # Addressフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。','error')
                form.token_address.data = token.token_address
                form.name.data = name
                form.symbol.data = symbol
                form.totalSupply.data = totalSupply
                form.abi.data = token.abi
                form.bytecode.data = token.bytecode
                return redirect(url_for('.setting', token_address=token_address))

            eth_unlock_account()

            # DEXアドレス変更
            if form.tradableExchange.data != tradableExchange:
                gas = TokenContract.estimateGas().\
                    setTradableExchange(to_checksum_address(form.tradableExchange.data))
                txid = TokenContract.functions.\
                    setTradableExchange(to_checksum_address(form.tradableExchange.data)).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

            # トークン詳細変更
            if form.details.data != details:
                gas = TokenContract.estimateGas().setDetails(form.details.data)
                txid = TokenContract.functions.setDetails(form.details.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

            # メモ欄変更
            if form.memo.data != memo:
                gas = TokenContract.estimateGas().setMemo(form.memo.data)
                txid = TokenContract.functions.setMemo(form.memo.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

            # 画像（小）変更
            if form.image_small.data != image_small:
                gas = TokenContract.estimateGas().setImageURL(0, form.image_small.data)
                txid_small = TokenContract.functions.setImageURL(0, form.image_small.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

            # 画像（中）変更
            if form.image_medium.data != image_medium:
                gas = TokenContract.estimateGas().setImageURL(1, form.image_medium.data)
                txid_medium = TokenContract.functions.setImageURL(1, form.image_medium.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

            # 画像（大）変更
            if form.image_large.data != image_large:
                gas = TokenContract.estimateGas().setImageURL(2, form.image_large.data)
                txid = TokenContract.functions.setImageURL(2, form.image_large.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            form.token_address.data = token.token_address
            form.name.data = name
            form.symbol.data = symbol
            form.totalSupply.data = totalSupply
            form.expirationDate.data = expirationDate
            form.transferable.data = transferable
            form.abi.data = token.abi
            form.bytecode.data = token.bytecode
            return render_template(
                'coupon/setting.html',
                form=form, token_address = token_address,
                isReleased = isReleased, isValid = isValid, token_name = name
            )
    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.details.data = details
        form.expirationDate.data = expirationDate
        form.transferable.data = transferable
        form.memo.data = memo
        form.tradableExchange.data = tradableExchange
        form.image_small.data = image_small
        form.image_medium.data = image_medium
        form.image_large.data = image_large
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'coupon/setting.html',
            form = form,
            token_address = token_address,
            token_name = name,
            isReleased = isReleased,
            isValid = isValid
        )

####################################################
# [クーポン]保有一覧（募集管理画面）
####################################################
@coupon.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('coupon/positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetCouponExchange', token_exchange_address)

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
                })

    return render_template('coupon/positions.html', position_list=position_list)

####################################################
# [クーポン]売出(募集)
####################################################
@coupon.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('coupon/sell')
    form = SellForm()

    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    details = TokenContract.functions.details().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    memo = TokenContract.functions.memo().call()
    transferable = TokenContract.functions.transferable().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    isValid = TokenContract.functions.isValid().call()

    owner = Config.ETH_ACCOUNT
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
            agent_address = Config.AGENT_ADDRESS

            deposit_gas = TokenContract.estimateGas().transfer(token_exchange_address, balance)
            TokenContract.functions.transfer(token_exchange_address, balance).\
                transact({'from':owner, 'gas':deposit_gas})

            ExchangeContract = Contract.get_contract(
                'IbetCouponExchange', token_exchange_address)

            sell_gas = ExchangeContract.estimateGas().\
                createOrder(token_address, balance, form.sellPrice.data, False, agent_address)
            ExchangeContract.functions.\
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
        form.details.data = details
        form.expirationDate.data = expirationDate
        form.memo.data = memo
        form.transferable.data = transferable
        form.status.data = isValid
        form.tradableExchange.data = tradableExchange
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template(
            'coupon/sell.html',
            token_address = token_address,
            token_name = name,
            form = form
        )

####################################################
# [クーポン]売出停止
####################################################
@coupon.route('/cancel_order/<string:token_address>', methods=['GET', 'POST'])
@login_required
def cancel_order(token_address):
    logger.info('coupon/cancel_order')
    form = CancelOrderForm()

    # トークンのABIを取得する
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.\
        get_contract('IbetCouponExchange', token_exchange_address)

    # 新規注文（NewOrder）のイベント情報を検索する
    event_filter = ExchangeContract.eventFilter(
        'NewOrder', {
            'filter':{
                'tokenAddress':token_address,
                'accountAddress':Config.ETH_ACCOUNT
            },
            'fromBlock':'earliest'
        }
    )

    entries = event_filter.get_all_entries()
    # キャンセル済みではない注文の注文IDを取得する
    for entry in entries:
        order_id_tmp = dict(entry['args'])['orderId']
        canceled = ExchangeContract.functions.orderBook(order_id_tmp).call()[6]
        if canceled == False:
            order_id = order_id_tmp

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            gas = ExchangeContract.estimateGas().cancelOrder(order_id)
            ExchangeContract.functions.cancelOrder(order_id).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            flash('募集停止処理を受け付けました。停止されるまでに数分程かかることがあります。', 'success')
            return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return redirect(url_for('.cancel_order', order_id=order_id))

    else: # GET
        # 注文情報を取得する
        orderBook = ExchangeContract.functions.orderBook(order_id).call()
        token_address = orderBook[1]
        amount = orderBook[2]
        price = orderBook[3]

        # トークンの商品名、略称、総発行量を取得する
        TokenContract = web3.eth.contract(
            address= to_checksum_address(token_address),
            abi = token_abi
        )
        name = TokenContract.functions.name().call()
        symbol = TokenContract.functions.symbol().call()
        totalSupply = TokenContract.functions.totalSupply().call()

        form.order_id.data = order_id
        form.token_address.data = token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.amount.data = amount
        form.price.data = price
        return render_template('coupon/cancel_order.html', form=form)

####################################################
# [クーポン]割当
####################################################
@coupon.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    logger.info('coupon/transfer')
    form = TransferCouponForm()
    if request.method == 'POST':
        if form.validate():
            # Addressフォーマットチェック（token_address）
            if not Web3.isAddress(form.tokenAddress.data):
                flash('クーポンアドレスは有効なアドレスではありません。','error')
                return render_template('coupon/transfer.html', form=form)

            # Addressフォーマットチェック（send_address）
            if not Web3.isAddress(form.sendAddress.data):
                flash('割当先アドレスは有効なアドレスではありません。','error')
                return render_template('coupon/transfer.html', form=form)

            eth_unlock_account()

            token = Token.query.\
                filter(Token.token_address==form.tokenAddress.data).first()
            token_abi = json.loads(
                token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            token_exchange_address = \
                Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS

            to_address = to_checksum_address(form.sendAddress.data)
            amount = form.sendAmount.data

            TokenContract = web3.eth.contract(
                address= token.token_address,
                abi = token_abi
            )

            # 取引所コントラクトへトークン送信
            deposit_gas = TokenContract.estimateGas().\
                allocate(token_exchange_address, amount)
            deposit_txid = TokenContract.functions.\
                allocate(token_exchange_address, amount).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':deposit_gas})

            # 取引所コントラクトからtransferで送信相手へ送信
            ExchangeContract = Contract.get_contract(
                'IbetCouponExchange', token_exchange_address)
            transfer_gas = ExchangeContract.estimateGas().\
                transfer(token.token_address, to_address, amount)
            transfer_txid = ExchangeContract.functions.\
                transfer(token.token_address, to_address, amount).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':transfer_gas})

            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/transfer.html', form=form)
        else:
            flash_errors(form)
            return render_template('coupon/transfer.html', form=form)
    else: # GET
        return render_template('coupon/transfer.html', form=form)

####################################################
# [クーポン]利用履歴
####################################################
@coupon.route('/usage_history/<string:token_address>', methods=['GET'])
@login_required
def usage_history(token_address):
    logger.info('coupon/usage_history')
    token_address, token_name, usage_list = \
        get_usege_history_coupon(token_address)

    return render_template(
        'coupon/usage_history.html',
        token_address = token_address,
        token_name = token_name,
        usage_list = usage_list
    )

####################################################
# [クーポン]保有者一覧
####################################################
@coupon.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('coupon/holders')
    holders, token_name = get_holders_coupon(token_address)
    return render_template('coupon/holders.html', \
        holders=holders, token_address=token_address, token_name=token_name)

####################################################
# [クーポン]保有者詳細
####################################################
@coupon.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('coupon/holder')
    personal_info = get_holder(token_address, account_address)
    return render_template('coupon/holder.html', personal_info=personal_info, token_address=token_address)

####################################################
# [クーポン]有効化/無効化
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
    eth_unlock_account()
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    gas = TokenContract.estimateGas().setStatus(isvalid)
    tx = TokenContract.functions.setStatus(isvalid).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':gas})

    flash('処理を受け付けました。完了までに数分程かかることがあります。', 'success')

#+++++++++++++++++++++++++++++++
# Custom Filter
#+++++++++++++++++++++++++++++++
@coupon.app_template_filter()
def format_date(date): # date = datetime object.
    if date:
        if isinstance(date, datetime):
            return date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(date, datetime.date):
            return date.strftime('%Y/%m/%d')
    return ''
