# -*- coding:utf-8 -*-
import json
import base64
import re
from datetime import datetime, date, timezone, timedelta

JST = timezone(timedelta(hours=+9), 'JST')
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
from .forms import IssueForm, SettingForm, AddSupplyForm

from web3 import Web3
from eth_utils import to_checksum_address
from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

from logging import getLogger

logger = getLogger('api')

ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'


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
                form.cancellationDate.data,
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
                        TokenContract.functions.setReferenceUrls(2, form.referenceUrls_3.data).transact(
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
    logger.info('share/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SHARE).all()

    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
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

            created = _to_jst(row.created) if row.created is not None else '--'

            token_list.append({
                'name': name,
                'symbol': symbol,
                'created': created,
                'tx_hash': row.tx_hash,
                'token_address': row.token_address,
                'status': status
            })
        except Exception as e:
            logger.exception(e)
            pass

    return render_template('share/list.html', tokens=token_list)


####################################################
# [株式]設定内容修正
####################################################
@share.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('share/setting')

    # 指定したトークンが存在しない場合、エラーを返す
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)

    # ABI参照
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # トークン情報の参照
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )
    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    issuePrice = TokenContract.functions.issuePrice().call()
    dividends, dividendRecordDate, dividendPaymentDate = TokenContract.functions.dividendInformation().call()
    cancellationDate = TokenContract.functions.cancellationDate().call()
    transferable = str(TokenContract.functions.transferable().call())
    memo = TokenContract.functions.memo().call()
    referenceUrls_1 = TokenContract.functions.referenceUrls(0).call()
    referenceUrls_2 = TokenContract.functions.referenceUrls(1).call()
    referenceUrls_3 = TokenContract.functions.referenceUrls(2).call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    personalInfoAddress = TokenContract.functions.personalInfoAddress().call()
    contact_information = TokenContract.functions.contactInformation().call()
    privacy_policy = TokenContract.functions.privacyPolicy().call()

    status = TokenContract.functions.status().call()
    offering_status = TokenContract.functions.offeringStatus().call()

    # TokenList登録状態取得
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract('TokenList', list_contract_address)
    token_struct = ListContract.functions.getTokenByAddress(token_address).call()
    is_released = False
    if token_struct[0] == token_address:
        is_released = True

    form = SettingForm()
    if request.method == 'POST':
        if form.validate():  # Validationチェック
            # EOAアンロック
            eth_unlock_account()

            # 1口あたりの配当金/分配金欄変更、権利確定日欄変更、配当支払日欄変更
            if form.dividends.data != dividends or form.dividendRecordDate.data != dividendRecordDate or \
                    form.dividendPaymentDate.data != dividendPaymentDate:
                gas = TokenContract.estimateGas().setDividendInformation(
                    form.dividends.data,
                    form.dividendRecordDate.data,
                    form.dividendPaymentDate.data
                )
                TokenContract.functions.setDividendInformation(
                    form.dividends.data,
                    form.dividendRecordDate.data,
                    form.dividendPaymentDate.data
                ). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 消却日欄変更
            if form.cancellationDate.data != cancellationDate:
                gas = TokenContract.estimateGas().setCancellationDate(form.cancellationDate.data)
                TokenContract.functions.setCancellationDate(form.cancellationDate.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 補足情報欄変更
            if form.memo.data != memo:
                gas = TokenContract.estimateGas().setMemo(form.memo.data)
                TokenContract.functions.setMemo(form.memo.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 譲渡制限変更
            if form.transferable.data != transferable:
                transferable_bool = True
                if form.transferable.data == 'False':
                    transferable_bool = False
                gas = TokenContract.estimateGas().setTransferable(transferable_bool)
                TokenContract.functions.setTransferable(transferable_bool). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

                # 関連URL変更
            if form.referenceUrls_1.data != referenceUrls_1:
                gas = TokenContract.estimateGas().setReferenceUrls(0, form.referenceUrls_1.data)
                TokenContract.functions.setReferenceUrls(0, form.referenceUrls_1.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            if form.referenceUrls_2.data != referenceUrls_2:
                gas = TokenContract.estimateGas().setReferenceUrls(1, form.referenceUrls_2.data)
                TokenContract.functions.setReferenceUrls(1, form.referenceUrls_2.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            if form.referenceUrls_3.data != referenceUrls_3:
                gas = TokenContract.estimateGas().setReferenceUrls(2, form.referenceUrls_3.data)
                TokenContract.functions.setReferenceUrls(2, form.referenceUrls_3.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # DEXアドレス変更
            if form.tradableExchange.data != tradableExchange:
                gas = TokenContract.estimateGas(). \
                    setTradableExchange(to_checksum_address(form.tradableExchange.data))
                TokenContract.functions. \
                    setTradableExchange(to_checksum_address(form.tradableExchange.data)). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # PersonalInfoコントラクトアドレス変更
            if form.personalInfoAddress.data != personalInfoAddress:
                gas = TokenContract.estimateGas(). \
                    setPersonalInfoAddress(to_checksum_address(form.personalInfoAddress.data))
                TokenContract.functions. \
                    setPersonalInfoAddress(to_checksum_address(form.personalInfoAddress.data)). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # 問い合わせ先変更
            if form.contact_information.data != contact_information:
                gas = TokenContract.estimateGas().setContactInformation(form.contact_information.data)
                TokenContract.functions.setContactInformation(form.contact_information.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            # プライバシーポリシー変更
            if form.privacy_policy.data != privacy_policy:
                gas = TokenContract.estimateGas().setPrivacyPolicy(form.privacy_policy.data)
                TokenContract.functions.setPrivacyPolicy(form.privacy_policy.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})

            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            # 変更不可能項目を再設定
            form.token_address.data = token.token_address
            form.name.data = name
            form.symbol.data = symbol
            form.totalSupply.data = totalSupply
            form.issuePrice.data = issuePrice
            form.abi.data = token.abi
            form.bytecode.data = token.bytecode
            return render_template(
                'share/setting.html',
                form=form,
                token_address=token_address,
                token_name=name,
                is_released=is_released,
                offering_status=offering_status,
                status=status
            )
    else:  # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.issuePrice.data = issuePrice
        form.dividends.data = dividends
        form.dividendRecordDate.data = dividendRecordDate
        form.dividendPaymentDate.data = dividendPaymentDate
        form.cancellationDate.data = cancellationDate
        form.transferable.data = transferable
        form.memo.data = memo
        form.referenceUrls_1.data = referenceUrls_1
        form.referenceUrls_2.data = referenceUrls_2
        form.referenceUrls_3.data = referenceUrls_3
        form.tradableExchange.data = tradableExchange
        form.personalInfoAddress.data = personalInfoAddress
        form.contact_information.data = contact_information
        form.privacy_policy.data = privacy_policy
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'share/setting.html',
            form=form,
            token_address=token_address,
            token_name=name,
            is_released=is_released,
            offering_status=offering_status,
            status=status
        )


####################################################
# [株式]公開
####################################################
@share.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('share/release')
    token_address = request.form.get('token_address')

    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract(
        'TokenList', list_contract_address)

    eth_unlock_account()

    try:
        gas = ListContract.estimateGas(). \
            register(token_address, 'IbetShare')
        ListContract.functions. \
            register(token_address, 'IbetShare'). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
    except ValueError:
        flash('既に公開されています。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.list'))


####################################################
# [株式]募集申込開始/停止
####################################################
@share.route('/start_offering', methods=['POST'])
@login_required
def start_offering():
    logger.info('share/start_offering')
    token_address = request.form.get('token_address')
    _set_offering_status(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@share.route('/stop_offering', methods=['POST'])
@login_required
def stop_offering():
    logger.info('share/stop_offering')
    token_address = request.form.get('token_address')
    _set_offering_status(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def _set_offering_status(token_address, status):
    eth_unlock_account()
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )
    try:
        gas = TokenContract.estimateGas().setOfferingStatus(status)
        tx = TokenContract.functions.setOfferingStatus(status). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.exception(e)
        flash('更新処理でエラーが発生しました。', 'error')


####################################################
# [株式]有効化/無効化
####################################################
@share.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info('share/valid')
    token_address = request.form.get('token_address')
    _set_validity(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@share.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info('share/invalid')
    token_address = request.form.get('token_address')
    _set_validity(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def _set_validity(token_address, isvalid):
    eth_unlock_account()
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    try:
        gas = TokenContract.estimateGas().setStatus(isvalid)
        tx = TokenContract.functions.setStatus(isvalid). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.exception(e)
        flash('更新処理でエラーが発生しました。', 'error')


####################################################
# [株式]追加発行
####################################################
@share.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info('share/add_supply')

    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(address=token.token_address, abi=token_abi)

    form = AddSupplyForm()
    form.token_address.data = token.token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.total_supply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()  # アカウントアンロック
            try:
                gas = TokenContract.estimateGas().issueFrom(Config.ETH_ACCOUNT, ZERO_ADDRESS, form.amount.data)
                tx_hash = TokenContract.functions.issueFrom(Config.ETH_ACCOUNT, ZERO_ADDRESS, form.amount.data). \
                    transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
                web3.eth.waitForTransactionReceipt(tx_hash)
            except Exception as e:
                logger.error(e)
                flash('処理に失敗しました。', 'error')
                return render_template(
                    'share/add_supply.html',
                    form=form,
                    token_address=token_address,
                    token_name=name
                )
            flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template(
                'share/add_supply.html',
                form=form,
                token_address=token_address,
                token_name=name
            )
    else:  # GET
        return render_template(
            'share/add_supply.html',
            form=form,
            token_address=token_address,
            token_name=name
        )


####################################################
# [株式]トークン追跡
####################################################
@share.route('/token/track/<string:token_address>', methods=['GET'])
@login_required
def token_tracker(token_address):
    logger.info('share/token_tracker')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address):
        abort(404)

    tracks = Transfer.query.filter(Transfer.token_address == token_address). \
        order_by(desc(Transfer.block_timestamp)). \
        all()

    track = []
    for row in tracks:
        try:
            timestamp_jst: datetime = _to_jst(row.block_timestamp)
            block_timestamp = timestamp_jst.strftime("%Y/%m/%d %H:%M:%S %z")
            track.append({
                'id': row.id,
                'transaction_hash': row.transaction_hash,
                'token_address': row.token_address,
                'account_address_from': row.account_address_from,
                'account_address_to': row.account_address_to,
                'transfer_amount': row.transfer_amount,
                'block_timestamp': block_timestamp,
            })
        except Exception as e:
            logger.exception(e)
            pass

    return render_template(
        'share/token_tracker.html',
        token_address=token_address,
        track=track
    )


####################################################
# [株式]募集申込一覧
####################################################
# 申込一覧画面
@share.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info('share/applications')
    # TODO: 実装する。templateでエラーが発生しないようにするためにダミーで作成している。
    return render_template(
        'share/applications.html',
        token_address=token_address,
    )


####################################################
# [株式]保有者一覧
####################################################
@share.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('share/holders')
    # TODO: 実装する。templateでエラーが発生しないようにするためにダミーで作成している。
    return render_template('share/holders.html', token_address=token_address)


####################################################
# 権限エラー
####################################################
@share.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')


####################################################
# 共通部品
####################################################
def _to_jst(src_datetime):
    """
    タイムゾーン情報（JST）を付与したdatetimeを返却する。

    :param src_datetime: JSTに変換する日時。タイムゾーンを持たない場合はUTCとみなす。
    注: Pythonの標準datetimeモジュールでは、タイムゾーンを持たないdatetimeはシステムロケールのタイムゾーンと判断する（日本ならJST）。
    この関数は標準モジュールと異なりUTCと判断する。
    :return: タイムゾーン情報がJSTのdatetime
    """

    if src_datetime is None:
        return None

    if src_datetime.tzinfo is None:
        # タイムゾーン情報を持たないdatetimeの場合（Naiveなdatetimeの場合）
        return src_datetime.replace(tzinfo=timezone.utc).astimezone(JST)
    else:
        # タイムゾーン情報が既にあるdatetimeの場合（Awareなdatetimeの場合）
        return src_datetime.astimezone(JST)
