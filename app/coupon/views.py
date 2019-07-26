# -*- coding:utf-8 -*-
import io
import os
import csv
import datetime
import traceback

from flask import request, redirect, url_for, flash, make_response
from flask import render_template
from flask_login import login_required
from sqlalchemy.orm import sessionmaker

from . import coupon
from .. import db
from ..util import *
from .forms import *
from ..models import CSVTransfer
from config import Config
from app.contracts import Contract

from logging import getLogger

logger = getLogger('api')

from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# +++++++++++++++++++++++++++++++
# Utils
# +++++++++++++++++++++++++++++++
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


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
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address == None:
                name = '--'
                symbol = '--'
                status = '--'
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
                status = TokenContract.functions.status().call()

            token_list.append({
                'name': name,
                'symbol': symbol,
                'status': status,
                'tx_hash': row.tx_hash,
                'created': row.created,
                'token_address': row.token_address
            })
        except Exception as e:
            logger.error(e)
            pass

    return render_template('coupon/list.html', tokens=token_list)


####################################################
# [クーポン]募集申込一覧
####################################################
@coupon.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info('coupon/applications')
    applications, token_name = get_applications(token_address)
    return render_template('coupon/applications.html', \
                           applications=applications, token_address=token_address, token_name=token_name)


def get_applications(token_address):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # 会員権Token
    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    # PersonalInfo
    personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
    PersonalInfoContract = \
        Contract.get_contract('PersonalInfo', personalinfo_address)

    try:
        event_filter = TokenContract.eventFilter(
            'ApplyFor', {
                'filter': {},
                'fromBlock': 'earliest'
            }
        )
        entries = event_filter.get_all_entries()
        list_temp = []
        for entry in entries:
            list_temp.append(entry['args']['accountAddress'])
    except:
        list_temp = []

    # 口座リストをユニークにする
    account_list = []
    for item in list_temp:
        if item not in account_list:
            account_list.append(item)

    token_owner = TokenContract.functions.owner().call()
    token_name = TokenContract.functions.name().call()

    applications = []
    for account_address in account_list:
        encrypted_info = PersonalInfoContract.functions. \
            personal_info(account_address, token_owner).call()[2]

        account_name = ''
        account_email_address = ''
        if encrypted_info == '' or cipher == None:
            pass
        else:
            ciphertext = base64.decodestring(encrypted_info.encode('utf-8'))
            try:
                message = cipher.decrypt(ciphertext)
                personal_info_json = json.loads(message)
                if 'name' in personal_info_json:
                    account_name = personal_info_json['name']
                if 'email' in personal_info_json:
                    account_email_address = personal_info_json['email']
            except:
                pass

        data = TokenContract.functions.applications(account_address).call()

        application = {
            'account_address': account_address,
            'account_name': account_name,
            'account_email_address': account_email_address,
            'data': data
        }
        applications.append(application)

    return applications, token_name


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
    ListContract = Contract. \
        get_contract('TokenList', list_contract_address)

    try:
        gas = ListContract.estimateGas(). \
            register(token_address, 'IbetCoupon')
        tx = ListContract.functions. \
            register(token_address, 'IbetCoupon'). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except ValueError:
        flash('既に公開されています。', 'error')

    return redirect(url_for('.setting', token_address=token_address))


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
            # Exchangeコントラクトのアドレスフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                return render_template('coupon/issue.html', form=form, form_description=form.description)

            # EOAアンロック
            eth_unlock_account()

            # トークン発行（トークンコントラクトのデプロイ）
            tmpVal = True
            if form.transferable.data == 'False':
                tmpVal = False

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                to_checksum_address(form.tradableExchange.data),
                form.details.data,
                form.return_details.data,
                form.memo.data,
                form.expirationDate.data,
                tmpVal,
                form.contact_information.data,
                form.privacy_policy.data
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetCoupon')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract('IbetCoupon', arguments, Config.ETH_ACCOUNT)

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_COUPON
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            # 商品画像URLの登録処理
            if form.image_1.data != '' or form.image_2.data != '' or form.image_3.data != '':
                # NOTE:トークン作成のトランザクションがブロックに取り込まれるまで待つ
                tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)

                if tx_receipt is not None:
                    TokenContract = web3.eth.contract(
                        address=tx_receipt['contractAddress'],
                        abi=abi
                    )
                    if form.image_1.data != '':
                        gas = TokenContract.estimateGas().setImageURL(0, form.image_1.data)
                        TokenContract.functions.setImageURL(0, form.image_1.data). \
                            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
                    if form.image_2.data != '':
                        gas = TokenContract.estimateGas().setImageURL(1, form.image_2.data)
                        TokenContract.functions.setImageURL(1, form.image_2.data). \
                            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
                    if form.image_3.data != '':
                        gas = TokenContract.estimateGas().setImageURL(2, form.image_3.data)
                        TokenContract.functions.setImageURL(2, form.image_3.data). \
                            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))

        else: # バリデーションエラー
            flash_errors(form)
            return render_template('coupon/issue.html', form=form, form_description=form.description)

    else: # GET
        return render_template('coupon/issue.html', form=form, form_description=form.description)


# 追加発行
@coupon.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info('coupon/add_supply')

    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )
    form = AddSupplyForm()
    form.token_address.data = token.token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.totalSupply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            if 100000000 >= (form.totalSupply.data + form.addSupply.data):
                eth_unlock_account()
                gas = TokenContract.estimateGas().issue(form.addSupply.data)
                TokenContract.functions.issue(form.addSupply.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
                flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
                return redirect(url_for('.list'))
            else:
                flash('総発行量と追加発行量の合計は、100,000,000が上限です。', 'error')
                return redirect(url_for('.add_supply', token_address=token_address))
        else:
            flash_errors(form)
            return render_template(
                'coupon/add_supply.html',
                form=form,
                token_address=token_address,
                token_name=name
            )
    else:  # GET
        return render_template(
            'coupon/add_supply.html',
            form=form,
            token_address=token_address,
            token_name=name
        )


####################################################
# [クーポン]設定内容修正
####################################################
@coupon.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('coupon/setting')

    # 指定したトークンが存在しない場合、エラーを返す
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)

    # ABI参照
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # トークン情報の参照
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )
    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    details = TokenContract.functions.details().call()
    return_details = TokenContract.functions.returnDetails().call()
    memo = TokenContract.functions.memo().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    status = TokenContract.functions.status().call()
    transferable = str(TokenContract.functions.transferable().call())
    image_1 = TokenContract.functions.getImageURL(0).call()
    image_2 = TokenContract.functions.getImageURL(1).call()
    image_3 = TokenContract.functions.getImageURL(2).call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    contact_information = TokenContract.functions.contactInformation().call()
    privacy_policy = TokenContract.functions.privacyPolicy().call()

    try:
        initial_offering_status = TokenContract.functions.initialOfferingStatus().call()
    except:
        initial_offering_status = False

    # TokenListへの登録有無
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract. \
        get_contract('TokenList', list_contract_address)
    token_struct = ListContract.functions. \
        getTokenByAddress(token_address).call()

    isReleased = False
    if token_struct[0] == token_address:
        isReleased = True

    form = SettingCouponForm()
    if request.method == 'POST':
        if form.validate():  # Validationチェック
            # Addressフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                form.token_address.data = token.token_address
                form.name.data = name
                form.symbol.data = symbol
                form.totalSupply.data = totalSupply
                form.abi.data = token.abi
                form.bytecode.data = token.bytecode
                return render_template(
                    'coupon/setting.html',
                    form=form, token_address=token_address,
                    isRelease=isReleased, status=status, token_name=name
                )

            # EOAアンロック
            eth_unlock_account()

            # DEXアドレス変更
            if form.tradableExchange.data != tradableExchange:
                gas = TokenContract.estimateGas(). \
                    setTradableExchange(to_checksum_address(form.tradableExchange.data))
                TokenContract.functions. \
                    setTradableExchange(to_checksum_address(form.tradableExchange.data)). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # トークン詳細変更
            if form.details.data != details:
                gas = TokenContract.estimateGas().setDetails(form.details.data)
                TokenContract.functions.setDetails(form.details.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # リターン詳細変更
            if form.return_details.data != return_details:
                gas = TokenContract.estimateGas().setReturnDetails(form.return_details.data)
                TokenContract.functions.setReturnDetails(form.return_details.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # メモ欄変更
            if form.memo.data != memo:
                gas = TokenContract.estimateGas().setMemo(form.memo.data)
                TokenContract.functions.setMemo(form.memo.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 有効期限変更
            if form.expirationDate.data != expirationDate:
                gas = TokenContract.estimateGas().setExpirationDate(form.expirationDate.data)
                TokenContract.functions.setExpirationDate(form.expirationDate.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 譲渡制限変更
            if form.transferable.data != transferable:
                transferable_bool = True
                if form.transferable.data == 'False':
                    transferable_bool = False
                gas = TokenContract.estimateGas().setTransferable(transferable_bool)
                TokenContract.functions.setTransferable(transferable_bool). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 画像変更
            if form.image_1.data != image_1:
                gas = TokenContract.estimateGas().setImageURL(0, form.image_1.data)
                TokenContract.functions.setImageURL(0, form.image_1.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            if form.image_2.data != image_2:
                gas = TokenContract.estimateGas().setImageURL(1, form.image_2.data)
                TokenContract.functions.setImageURL(1, form.image_2.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            if form.image_3.data != image_3:
                gas = TokenContract.estimateGas().setImageURL(2, form.image_3.data)
                TokenContract.functions.setImageURL(2, form.image_3.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 問い合わせ先変更
            if form.contact_information.data != contact_information:
                gas = TokenContract.estimateGas().setContactInformation(form.contact_information.data)
                TokenContract.functions.setContactInformation(form.contact_information.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # プライバシーポリシー
            if form.privacy_policy.data != privacy_policy:
                gas = TokenContract.estimateGas().setPrivacyPolicy(form.privacy_policy.data)
                TokenContract.functions.setPrivacyPolicy(form.privacy_policy.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            form.token_address.data = token.token_address
            form.name.data = name
            form.symbol.data = symbol
            form.totalSupply.data = totalSupply
            form.abi.data = token.abi
            form.bytecode.data = token.bytecode
            return render_template(
                'coupon/setting.html',
                form=form, token_address=token_address,
                isReleased=isReleased, status=status, token_name=name
            )
    else:  # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.details.data = details
        form.return_details.data = return_details
        form.expirationDate.data = expirationDate
        form.transferable.data = transferable
        form.memo.data = memo
        form.tradableExchange.data = tradableExchange
        form.image_1.data = image_1
        form.image_2.data = image_2
        form.image_3.data = image_3
        form.contact_information.data = contact_information
        form.privacy_policy.data = privacy_policy
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'coupon/setting.html',
            form=form,
            token_address=token_address,
            token_name=name,
            isReleased=isReleased,
            status=status,
            initial_offering_status=initial_offering_status
        )


####################################################
# [クーポン]保有一覧（売出管理画面）
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
                abi=json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            )

            owner = to_checksum_address(row.admin_address)

            # 自身が保有している預かりの残高を取得
            balance = TokenContract.functions.balanceOf(owner).call()

            # 拘束中数量を取得する
            commitment = ExchangeContract.functions. \
                commitmentOf(owner, row.token_address).call()

            # 拘束数量がゼロよりも大きい場合、売出中のステータスを返す
            on_sale = False
            if balance == 0:
                on_sale = True

            # 残高がゼロよりも大きい場合、または売出中のステータスの場合、リストを返す
            if balance > 0 or on_sale == True:
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                totalSupply = TokenContract.functions.totalSupply().call()
                position_list.append({
                    'token_address': row.token_address,
                    'name': name,
                    'symbol': symbol,
                    'totalSupply': totalSupply,
                    'balance': balance,
                    'created': row.created,
                    'commitment': commitment,
                    'on_sale': on_sale,
                })

    return render_template('coupon/positions.html', position_list=position_list)


####################################################
# [クーポン]売出
####################################################
@coupon.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('coupon/sell')
    form = SellForm()

    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    details = TokenContract.functions.details().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    memo = TokenContract.functions.memo().call()
    transferable = TokenContract.functions.transferable().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    status = TokenContract.functions.status().call()

    owner = Config.ETH_ACCOUNT
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
            agent_address = Config.AGENT_ADDRESS

            deposit_gas = TokenContract.estimateGas().transfer(token_exchange_address, balance)
            TokenContract.functions.transfer(token_exchange_address, balance). \
                transact({'from': owner, 'gas': deposit_gas})

            ExchangeContract = Contract.get_contract(
                'IbetCouponExchange', token_exchange_address)

            sell_gas = ExchangeContract.estimateGas(). \
                createOrder(token_address, balance, form.sellPrice.data, False, agent_address)
            txid = ExchangeContract.functions. \
                createOrder(token_address, balance, form.sellPrice.data, False, agent_address). \
                transact({'from': owner, 'gas': sell_gas})
            tx = web3.eth.waitForTransactionReceipt(txid)
            flash('新規売出を受け付けました。売出開始までに数分程かかることがあります。', 'success')
            return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return redirect(url_for('.sell', token_address=token_address))

    else:  # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.details.data = details
        form.expirationDate.data = expirationDate
        form.memo.data = memo
        form.transferable.data = transferable
        form.status.data = status
        form.tradableExchange.data = tradableExchange
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template(
            'coupon/sell.html',
            token_address=token_address,
            token_name=name,
            form=form
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
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract. \
        get_contract('IbetCouponExchange', token_exchange_address)

    # 新規注文（NewOrder）のイベント情報を検索する
    event_filter = ExchangeContract.eventFilter(
        'NewOrder', {
            'filter': {
                'tokenAddress': token_address,
                'accountAddress': Config.ETH_ACCOUNT
            },
            'fromBlock': 'earliest'
        }
    )

    entries = event_filter.get_all_entries()
    # キャンセル済みではない注文の注文IDを取得する
    for entry in entries:
        order_id_tmp = dict(entry['args'])['orderId']
        canceled = ExchangeContract.functions.getOrder(order_id_tmp).call()[6]
        if canceled == False:
            order_id = order_id_tmp

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            gas = ExchangeContract.estimateGas().cancelOrder(order_id)
            txid = ExchangeContract.functions.cancelOrder(order_id). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            tx = web3.eth.waitForTransactionReceipt(txid)
            flash('売出停止処理を受け付けました。停止されるまでに数分程かかることがあります。', 'success')
            return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return redirect(url_for('.cancel_order', order_id=order_id))

    else:  # GET
        # 注文情報を取得する
        orderBook = ExchangeContract.functions.getOrder(order_id).call()
        token_address = orderBook[1]
        amount = orderBook[2]
        price = orderBook[3]

        # トークンの商品名、略称、総発行量を取得する
        TokenContract = web3.eth.contract(
            address=to_checksum_address(token_address),
            abi=token_abi
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
# 割当
@coupon.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    logger.info('coupon/transfer')
    form = TransferForm()

    if request.method == 'POST':
        if form.validate():
            # Addressフォーマットチェック（token_address）
            if not Web3.isAddress(form.token_address.data):
                flash('クーポンアドレスは有効なアドレスではありません。', 'error')
                return render_template('coupon/transfer.html', form=form)

            # Addressフォーマットチェック（send_address）
            if not Web3.isAddress(form.to_address.data):
                flash('割当先アドレスは有効なアドレスではありません。', 'error')
                return render_template('coupon/transfer.html', form=form)

            eth_unlock_account()

            # Tokenコントラクト接続
            token = Token.query. \
                filter(Token.token_address == form.token_address.data).first()
            token_abi = json.loads(
                token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            token_exchange_address = \
                Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
            TokenContract = web3.eth.contract(
                address=token.token_address,
                abi=token_abi
            )

            # 割当処理（発行体アドレス→指定アドレス）
            from_address = Config.ETH_ACCOUNT
            to_address = to_checksum_address(form.to_address.data)
            amount = form.amount.data
            tx_hash = transfer_token(TokenContract, from_address, to_address, amount)

            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/transfer.html', form=form)
        else:
            flash_errors(form)
            return render_template('coupon/transfer.html', form=form)
    else:  # GET
        return render_template('coupon/transfer.html', form=form)


# 割当（CSV一括）
@coupon.route('/bulk_transfer', methods=['GET', 'POST'])
@login_required
def bulk_transfer():
    logger.info('coupon/bulk_transfer')
    form = BulkTransferForm()
    transfer_set = []

    if request.method == 'POST':
        if form.validate():
            send_data = request.files['transfer_csv']
            transfer_set = []
            try:
                stream = io.StringIO(send_data.stream.read().decode("UTF8"), newline=None)
                csv_input = csv.reader(stream)
                for row in csv_input:
                    transfer_set.append(row)
                logger.info(transfer_set)

            except Exception as e:
                logger.error(e)
                flash('CSVアップロードでエラーが発生しました。', 'error')
                transfer_set = "error"
                return render_template('coupon/bulk_transfer.html', form=form, transfer_set=transfer_set)

            # transfer_rowの構成：[coupon_address, to_address, amount]
            for transfer_row in transfer_set:
                # Addressフォーマットチェック（token_address）
                if not Web3.isAddress(transfer_row[0]):
                    flash('無効なクーポンアドレスが含まれています。', 'error')
                    message = '無効なクーポンアドレスが含まれています。' + transfer_row[0]
                    logger.warning(message)
                    return render_template('coupon/bulk_transfer.html', form=form)

                # Addressフォーマットチェック（send_address）
                if not Web3.isAddress(transfer_row[1]):
                    flash('無効な割当先アドレスが含まれています。', 'error')
                    message = '無効な割当先アドレスが含まれています' + transfer_row[1]
                    logger.warning(message)
                    return render_template('coupon/bulk_transfer.html', form=form)

                # amountチェック
                if 100000000 < int(transfer_row[2]):
                    flash('割当量が適切ではありません。', 'error')
                    message = '割当量が適切ではありません' + transfer_row[2]
                    logger.warning(message)
                    return render_template('coupon/bulk_transfer.html', form=form)

                # DB登録処理
                csvtransfer = CSVTransfer()
                csvtransfer.coupon_address = transfer_row[0]
                csvtransfer.to_address = transfer_row[1]
                csvtransfer.amount = transfer_row[2]
                csvtransfer.transferred = False
                db.session.add(csvtransfer)

            # 全てのデータが正常処理されたらコミットを行う
            db.session.commit()

            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return render_template('coupon/bulk_transfer.html', form=form, transfer_set=transfer_set)

        else:
            flash_errors(form)
            return render_template('coupon/bulk_transfer.html', form=form, transfer_set=transfer_set)

    else:  # GET
        return render_template('coupon/bulk_transfer.html', form=form)


# サンプルCSVダウンロード
@coupon.route('/sample_csv_download', methods=['POST'])
@login_required
def sample_csv_download():
    logger.info('coupon/transfer_csv_download')

    f = io.StringIO()
    # データ行
    data_row = \
        '0x0b3c7F97383bCFf942E6b1038a47B9AA5377A252,0xF37aF18966609eCaDe3E4D1831996853c637cfF3,10' \
        + '\n' \
        + '0xC362102bC5bbA9fBd0F2f5d397f3644Aa32b3bA8,0xF37aF18966609eCaDe3E4D1831996853c637cfF3,20'

    f.write(data_row)

    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + 'transfer_list.csv'
    return res


# 割当（募集申込）
@coupon.route(
    '/allocate/<string:token_address>/<string:account_address>',
    methods=['GET', 'POST'])
@login_required
def allocate(token_address, account_address):
    logger.info('coupon/allocate')

    # アドレスのフォーマットチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # Tokenコントラクト接続
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(address=token.token_address, abi=token_abi)

    form = TransferForm()
    form.token_address.data = token_address
    form.to_address.data = account_address
    if request.method == 'POST':
        if form.validate():
            # 残高チェック
            amount = int(form.amount.data)
            balance = TokenContract.functions. \
                balanceOf(to_checksum_address(Config.ETH_ACCOUNT)).call()
            if amount > balance:
                flash('移転数量が残高を超えています。', 'error')
                return render_template(
                    'coupon/allocate.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            # 割当処理（発行体アドレス→指定アドレス）
            from_address = Config.ETH_ACCOUNT
            to_address = to_checksum_address(account_address)
            tx_hash = transfer_token(TokenContract, from_address, to_address, amount)

            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.applications', token_address=token_address))
        else:
            flash_errors(form)
            return render_template(
                'coupon/allocate.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        return render_template(
            'coupon/allocate.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


def transfer_token(TokenContract, from_address, to_address, amount):
    eth_unlock_account()
    token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetCouponExchange', token_exchange_address)

    # 取引所コントラクトへトークン送信
    deposit_gas = TokenContract.estimateGas(). \
        transferFrom(from_address, token_exchange_address, amount)
    TokenContract.functions. \
        transferFrom(from_address, token_exchange_address, amount). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})

    # 取引所コントラクトからtransferで送信相手へ送信
    transfer_gas = ExchangeContract.estimateGas(). \
        transfer(to_checksum_address(TokenContract.address), to_address, amount)
    tx_hash = ExchangeContract.functions. \
        transfer(to_checksum_address(TokenContract.address), to_address, amount). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': transfer_gas})
    return tx_hash


####################################################
# [クーポン]保有者移転
####################################################
@coupon.route(
    '/transfer_ownership/<string:token_address>/<string:account_address>',
    methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info('coupon/transfer_ownership')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # ABI参照
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    # 残高参照
    balance = TokenContract.functions. \
        balanceOf(to_checksum_address(account_address)).call()

    form = TransferOwnershipForm()
    if request.method == 'POST':
        if form.validate():
            from_address = to_checksum_address(account_address)
            to_address = to_checksum_address(form.to_address.data)
            amount = int(form.amount.data)

            if amount > balance:
                flash('移転数量が残高を超えています。', 'error')
                form.from_address.data = from_address
                return render_template(
                    'coupon/transfer_ownership.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            eth_unlock_account()
            token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
            ExchangeContract = Contract.get_contract(
                'IbetCouponExchange', token_exchange_address)

            deposit_gas = TokenContract.estimateGas(). \
                transferFrom(from_address, token_exchange_address, amount)
            TokenContract.functions. \
                transferFrom(from_address, token_exchange_address, amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})

            transfer_gas = ExchangeContract.estimateGas(). \
                transfer(to_checksum_address(token_address), to_address, amount)
            txid = ExchangeContract.functions. \
                transfer(to_checksum_address(token_address), to_address, amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': transfer_gas})

            tx = web3.eth.waitForTransactionReceipt(txid)
            return redirect(url_for('.holders', token_address=token_address))
        else:
            flash_errors(form)
            form.from_address.data = account_address
            return render_template(
                'coupon/transfer_ownership.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        form.from_address.data = account_address
        form.to_address.data = ''
        form.amount.data = balance
        return render_template(
            'coupon/transfer_ownership.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


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
        token_address=token_address,
        token_name=token_name,
        usage_list=usage_list
    )


# クーポントークンの利用履歴を返す
def get_usege_history_coupon(token_address):
    # Coupon Token Contract
    # Note: token_addressに対して、Couponトークンのものであるかはチェックしていない。
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"'). \
                           replace('True', 'true').replace('False', 'false'))
    CouponContract = web3.eth.contract(
        address=token_address, abi=token_abi)

    # クーポン名を取得
    token_name = CouponContract.functions.name().call()

    # クーポントークンの消費イベント（Consume）を検索
    try:
        event_filter = CouponContract.eventFilter(
            'Consume', {
                'filter': {},
                'fromBlock': 'earliest'
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
                web3.eth.getBlock(entry['blockNumber'])['timestamp'], JST). \
                strftime("%Y/%m/%d %H:%M:%S"),
            'consumer': entry['args']['consumer'],
            'value': entry['args']['value']
        }
        usage_list.append(usage)

    return token_address, token_name, usage_list


# 利用履歴リストCSVダウンロード
@coupon.route('/used_csv_download', methods=['POST'])
@login_required
def used_csv_download():
    logger.info('coupon/used_csv_download')

    token_address = request.form.get('token_address')
    # token_address, token_name, usage_list = get_usege_history_coupon(token_address)

    # for debug ----------------------------------
    token_address = "0x116Cd7643efcF4AF0963002b66a6CD74a9cd4Cd3"
    token_name = "クーポンTEST"
    usage_list = [
        {
            'block_timestamp': "2019/06/20 16:10:18",
            'consumer': "0x61C80E8834Aa2360F760F71B84ae7B46F7bFfc8a",
            'value': 1
        },
        {
            'block_timestamp': "2019/06/20 16:10:18",
            'consumer': "0x61C80E8834Aa2360F760F71B84ae7B46F7bFfc8a",
            'value': 1
        }
    ]
    # --------------------------------------------

    f = io.StringIO()
    for usage in usage_list:
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + str(usage["block_timestamp"]) + ',' + usage["consumer"] + ',' \
            + str(usage["value"]) + '\n'
        f.write(data_row)
        logger.info(usage)

    now = datetime.now()
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") + \
        'coupon_used_list.csv'
    return res


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
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
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
            'filter': {},
            'fromBlock': 'earliest'
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
            encrypted_info = PersonalInfoContract.functions. \
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
                'account_address': account_address,
                'name': name,
                'balance': balance,
                'used': used
            }
            holders.append(holder)

    return holders, token_name


# 保有者リストCSVダウンロード
@coupon.route('/holders_csv_download', methods=['POST'])
@login_required
def holders_csv_download():
    logger.info('coupon/holders_csv_download')

    token_address = request.form.get('token_address')
    holders, token_name = get_holders_coupon(token_address)

    # for debug
    logger.info(token_name)

    f = io.StringIO()
    for holder in holders:
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + holder["account_address"] + ',' + str(holder["balance"]) + ',' + \
                str(holder["balance"]) + ',' + str(holder["used"]) + '\n'
        f.write(data_row)
        logger.info(holder)

    now = datetime.now()
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") + \
        'coupon_holders_list.csv'
    return res


####################################################
# [クーポン]保有者詳細
####################################################
@coupon.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('coupon/holder')
    personal_info = get_holder(token_address, account_address)
    return render_template(
        'coupon/holder.html',
        personal_info=personal_info,
        token_address=token_address)


###################################################
# [クーポン]有効化/無効化
####################################################
@coupon.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info('coupon/valid')
    token_address = request.form.get('token_address')
    coupon_valid(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@coupon.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info('coupon/invalid')
    token_address = request.form.get('token_address')
    coupon_valid(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def coupon_valid(token_address, status):
    eth_unlock_account()
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    try:
        gas = TokenContract.estimateGas().setStatus(status)
        tx = TokenContract.functions.setStatus(status). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.error(e)
        flash('更新処理でエラーが発生しました。', 'error')


####################################################
# [クーポン]募集申込開始/停止
####################################################
@coupon.route('/start_initial_offering', methods=['POST'])
@login_required
def start_initial_offering():
    logger.info('coupon/start_initial_offering')
    token_address = request.form.get('token_address')
    set_initial_offering_status(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@coupon.route('/stop_initial_offering', methods=['POST'])
@login_required
def stop_initial_offering():
    logger.info('coupon/stop_initial_offering')
    token_address = request.form.get('token_address')
    set_initial_offering_status(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def set_initial_offering_status(token_address, status):
    eth_unlock_account()
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    try:
        gas = TokenContract.estimateGas().setInitialOfferingStatus(status)
        tx = TokenContract.functions.setInitialOfferingStatus(status). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.error(e)
        flash('更新処理でエラーが発生しました。', 'error')


# +++++++++++++++++++++++++++++++
# Custom Filter
# +++++++++++++++++++++++++++++++
@coupon.app_template_filter()
def format_date(date):  # date = datetime object.
    if date:
        if isinstance(date, datetime):
            return date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(date, datetime.date):
            return date.strftime('%Y/%m/%d')
    return ''
