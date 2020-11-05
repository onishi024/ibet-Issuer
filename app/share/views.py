"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

import json
import re
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=+9), 'JST')
import io
import time

from flask_wtf import FlaskForm as Form
from flask import request, redirect, url_for, flash, make_response, render_template, abort, jsonify, session
from flask_login import login_required
from sqlalchemy import desc

from app import db
from app.models import Token, Transfer, AddressType, ApplyFor, Issuer, HolderList, PersonalInfoContract
from app.models import PersonalInfo as PersonalInfoModel
from app.utils import ContractUtils, TokenUtils
from app.exceptions import EthRuntimeError
from config import Config
from . import share
from .forms import IssueForm, SettingForm, AddSupplyForm, TransferOwnershipForm, TransferForm, AllotForm

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
def flash_errors(form: Form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


####################################################
# [株式]トークン名取得
####################################################
@share.route('/get_token_name/<string:token_address>', methods=['GET'])
@login_required
def get_token_name(token_address):
    logger.info('share/get_token_name')
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'], Config.TEMPLATE_ID_SHARE)
    token_name = TokenContract.functions.name().call()

    return jsonify(token_name)


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
            # 1株配当の値が未設定の場合、0を設定
            if form.dividends.data is None:
                form.dividends.data = 0

            # 1株配当：小数点有効桁数チェック
            if not form.check_decimal_places(2, form.dividends):
                flash('１株配当は小数点2桁以下で入力してください。', 'error')
                return render_template('share/issue.html', form=form, form_description=form.description)

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
                int(form.dividends.data * 100),
                form.dividendRecordDate.data,
                form.dividendPaymentDate.data,
                form.cancellationDate.data,
                form.contact_information.data,
                form.privacy_policy.data,
                form.memo.data,
                bool_transferable
            ]

            _, bytecode, bytecode_runtime = ContractUtils.get_contract_info('IbetShare')
            contract_address, abi, tx_hash = \
                ContractUtils.deploy_contract('IbetShare', arguments, session["eth_account"])

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_SHARE
            token.tx_hash = tx_hash
            token.admin_address = session['eth_account'].lower()
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            # 関連URLの登録処理
            if form.referenceUrls_1.data != '' or form.referenceUrls_2.data != '' or form.referenceUrls_3.data != '':
                # トークンが正常にデプロイされた後に画像URLの登録処理を実行する
                if contract_address is not None:
                    TokenContract = web3.eth.contract(address=contract_address, abi=abi)
                    if form.referenceUrls_1.data != '':
                        tx = TokenContract.functions.setReferenceUrls(0, form.referenceUrls_1.data). \
                            buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
                    if form.referenceUrls_2.data != '':
                        tx = TokenContract.functions.setReferenceUrls(1, form.referenceUrls_2.data). \
                            buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
                    if form.referenceUrls_3.data != '':
                        tx = TokenContract.functions.setReferenceUrls(2, form.referenceUrls_3.data). \
                            buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('share/issue.html', form=form, form_description=form.description)
    else:  # GET
        issuer = Issuer.query.get(session["issuer_id"])
        form.tradableExchange.data = issuer.ibet_share_exchange_contract_address
        form.personalInfoAddress.data = issuer.personal_info_contract_address
        return render_template('share/issue.html', form=form, form_description=form.description)


####################################################
# [株式]発行済一覧
####################################################
@share.route('/list', methods=['GET'])
@login_required
def list():
    logger.info('share/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_SHARE,
        # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
        admin_address=session["eth_account"].lower()
    ).all()

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

            created = _to_jst(row.created).strftime("%Y/%m/%d %H:%M:%S %z") if row.created is not None else '--'

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
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session["eth_account"].lower()). \
        first()
    if token is None:
        abort(404)

    # ABI参照
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # 発行体情報
    issuer = Issuer.query.get(session["issuer_id"])

    # トークン情報の参照
    TokenContract = web3.eth.contract(address=token.token_address, abi=token_abi)
    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    issuePrice = TokenContract.functions.issuePrice().call()
    dividends, dividendRecordDate, dividendPaymentDate = TokenContract.functions.dividendInformation().call()
    dividends = dividends * 0.01
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
    list_contract_address = issuer.token_list_contract_address
    ListContract = ContractUtils.get_contract('TokenList', list_contract_address)
    token_struct = ListContract.functions.getTokenByAddress(token_address).call()
    is_released = False
    if token_struct[0] == token_address:
        is_released = True

    form = SettingForm()
    if request.method == 'POST':
        if form.validate():  # Validationチェック
            # 1株配当の値が未設定の場合、0を設定
            if form.dividends.data is None:
                form.dividends.data = 0

            # 1株配当：小数点有効桁数チェック
            if not form.check_decimal_places(2, form.dividends):
                flash('１株配当は小数点2桁以下で入力してください。', 'error')
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

            # １株配当欄変更、権利確定日欄変更、配当支払日欄変更
            if float(form.dividends.data) != dividends or \
                    form.dividendRecordDate.data != dividendRecordDate or \
                    form.dividendPaymentDate.data != dividendPaymentDate:
                tx = TokenContract.functions.setDividendInformation(
                    int(form.dividends.data * 100),
                    form.dividendRecordDate.data,
                    form.dividendPaymentDate.data
                ).buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 消却日欄変更
            if form.cancellationDate.data != cancellationDate:
                tx = TokenContract.functions.setCancellationDate(form.cancellationDate.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 補足情報欄変更
            if form.memo.data != memo:
                tx = TokenContract.functions.setMemo(form.memo.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 譲渡制限変更
            if form.transferable.data != transferable:
                transferable_bool = True
                if form.transferable.data == 'False':
                    transferable_bool = False
                tx = TokenContract.functions.setTransferable(transferable_bool). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 関連URL変更
            if form.referenceUrls_1.data != referenceUrls_1:
                tx = TokenContract.functions.setReferenceUrls(0, form.referenceUrls_1.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            if form.referenceUrls_2.data != referenceUrls_2:
                tx = TokenContract.functions.setReferenceUrls(1, form.referenceUrls_2.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            if form.referenceUrls_3.data != referenceUrls_3:
                tx = TokenContract.functions.setReferenceUrls(2, form.referenceUrls_3.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # DEXアドレス変更
            if form.tradableExchange.data != tradableExchange:
                tx = TokenContract.functions. \
                    setTradableExchange(to_checksum_address(form.tradableExchange.data)). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # PersonalInfoコントラクトアドレス変更
            if form.personalInfoAddress.data != personalInfoAddress:
                tx = TokenContract.functions. \
                    setPersonalInfoAddress(to_checksum_address(form.personalInfoAddress.data)). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 問い合わせ先変更
            if form.contact_information.data != contact_information:
                tx = TokenContract.functions.setContactInformation(form.contact_information.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # プライバシーポリシー変更
            if form.privacy_policy.data != privacy_policy:
                tx = TokenContract.functions.setPrivacyPolicy(form.privacy_policy.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

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

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    issuer = Issuer.query.get(session["issuer_id"])
    list_contract_address = issuer.token_list_contract_address
    ListContract = ContractUtils.get_contract('TokenList', list_contract_address)
    try:
        tx = ListContract.functions.register(token_address, 'IbetShare'). \
            buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
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
    """
    募集申込ステータス変更
    :param token_address: トークンアドレス
    :param status: 変更後ステータス
    :return: なし
    """
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'], template_id=Config.TEMPLATE_ID_SHARE)
    try:
        tx = TokenContract.functions.setOfferingStatus(status). \
            buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
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
    """
    取扱ステータス変更
    :param token_address: トークンアドレス
    :param status: 変更後ステータス
    :return: なし
    """
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'], template_id=Config.TEMPLATE_ID_SHARE)
    try:
        tx = TokenContract.functions.setStatus(isvalid). \
            buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
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

    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'], template_id=Config.TEMPLATE_ID_SHARE)

    form = AddSupplyForm()
    form.token_address.data = token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.total_supply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            try:
                tx = TokenContract.functions.issueFrom(session["eth_account"], Config.ZERO_ADDRESS, form.amount.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            except Exception as e:
                logger.exception(e)
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

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
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
    return render_template(
        'share/applications.html',
        token_address=token_address,
    )


# 申込者リストCSVダウンロード
@share.route('/applications_csv_download', methods=['POST'])
@login_required
def applications_csv_download():
    logger.info('share/applications_csv_download')

    token_address = request.form.get('token_address')
    application = json.loads(get_applications(token_address).data)
    token_name = json.loads(get_token_name(token_address).data)

    f = io.StringIO()

    # ヘッダー行
    data_header = \
        'token_name,' + \
        'token_address,' + \
        'account_address,' + \
        'name,' + \
        'email,' + \
        'code,' + \
        'requested_amount\n'
    f.write(data_header)

    for item in application:
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + item["account_address"] + ',' + \
            item["account_name"] + ',' + item["account_email_address"] + ',' + item["data"] + ',' + \
            str(item["requested_amount"]) + '\n'
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = \
        'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") + 'share_applications_list.csv'
    return res


# 申込一覧取得
@share.route('/get_applications/<string:token_address>', methods=['GET'])
@login_required
def get_applications(token_address):
    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=session['eth_account'],
        template_id=Config.TEMPLATE_ID_SHARE
    )

    # PersonalInfoコントラクト接続
    try:
        personal_info_address = TokenContract.functions.personalInfoAddress().call()
    except Exception as e:
        logger.exception(e)
        personal_info_address = Config.ZERO_ADDRESS

    personal_info_contract = PersonalInfoContract(
        issuer_address=session['eth_account'],
        custom_personal_info_address=personal_info_address
    )

    # 申込（ApplyFor）イベントを検索
    apply_for_events = ApplyFor.query. \
        distinct(ApplyFor.account_address). \
        filter(ApplyFor.token_address == token_address).all()

    # 募集申込の履歴が存在するアカウントアドレスのリストを作成
    account_list = []
    for event in apply_for_events:
        account_list.append(event.account_address)

    applications = []
    for account_address in account_list:
        # 個人情報取得
        personal_info = personal_info_contract.get_info(
            account_address=account_address,
            default_value="--"
        )

        application_data = TokenContract.functions.applications(account_address).call()
        balance = TokenContract.functions.balanceOf(to_checksum_address(account_address)).call()
        application = {
            'account_address': account_address,
            'account_name': personal_info['name'],
            'account_email_address': personal_info['email'],
            'requested_amount': application_data[0],
            'allotted_amount': application_data[1],
            'data': application_data[2],
            'balance': balance
        }
        applications.append(application)

    return jsonify(applications)


####################################################
# [株式]割当登録
####################################################
@share.route('/allot/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def allot(token_address, account_address):
    """
    募集申込割当登録

    :param token_address: トークンアドレス
    :param account_address: 割当対象のアカウントアドレス
    """
    logger.info('share/allot')

    # アドレスのフォーマットチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    form = AllotForm()
    form.token_address.data = token_address
    form.to_address.data = account_address

    if request.method == 'POST':
        if form.validate():
            # 割当処理
            to_address = to_checksum_address(account_address)
            try:
                tx = TokenContract.functions.allot(to_address, form.amount.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
                # NOTE: 募集申込一覧が非同期で更新されるため、5秒待つ
                time.sleep(5)
                flash('処理を受け付けました。', 'success')
                return redirect(url_for('.applications', token_address=token_address))
            except Exception as e:
                logger.exception(e)
                flash('処理に失敗しました。', 'error')
                return _render_allot(token_address, account_address, form)
        else:
            flash_errors(form)

    return _render_allot(token_address, account_address, form)


# 割当登録画面
def _render_allot(token_address: str, account_address: str, form: AllotForm):
    return render_template(
        'share/allot.html',
        token_address=token_address,
        account_address=account_address,
        form=form
    )


####################################################
# [株式]権利移転（募集申込）
####################################################
@share.route('/transfer_allotment/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_allotment(token_address, account_address):
    """
    募集申込割当登録

    :param token_address: トークンアドレス
    :param account_address: 移転先のアカウントアドレス
    """
    logger.info('share/transfer_allotment')

    # アドレスのフォーマットチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    # 割当数量を取得
    allotted_amount = TokenContract.functions.applications(account_address).call()[1]

    form = TransferForm()
    form.token_address.data = token_address
    form.to_address.data = account_address
    form.amount.data = allotted_amount

    if request.method == 'POST':
        if form.validate():
            # 残高チェック：割当数量が残高を超過している場合はエラー
            amount = int(form.amount.data)
            balance = TokenContract.functions.balanceOf(session["eth_account"]).call()
            if amount > balance:
                flash('移転数量が残高を超えています。', 'error')
                return _render_transfer_allotment(token_address, account_address, form)

            from_address = session["eth_account"]
            to_address = to_checksum_address(account_address)
            try:
                # 強制移転
                tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
                # NOTE: 募集申込一覧が非同期で更新されるため、5秒待つ
                time.sleep(5)
                flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
                return redirect(url_for('.applications', token_address=token_address))
            except Exception as e:
                logger.exception(e)
                flash('処理に失敗しました。', 'error')
                return _render_transfer_allotment(token_address, account_address, form)
        else:
            flash_errors(form)

    return _render_transfer_allotment(token_address, account_address, form)


# 権利移転（募集申込）
def _render_transfer_allotment(token_address: str, account_address: str, form: TransferForm):
    return render_template(
        'share/transfer_allotment.html',
        token_address=token_address,
        account_address=account_address,
        form=form
    )


####################################################
# [株式]保有者一覧
####################################################
@share.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('share/holders')

    return render_template(
        'share/holders.html',
        token_address=token_address
    )


# 保有者リストCSVダウンロード
@share.route('/holders_csv_download', methods=['POST'])
@login_required
def holders_csv_download():
    logger.info('share/holders_csv_download')

    token_address = request.form.get('token_address')
    holders = json.loads(get_holders(token_address).data)
    token_name = json.loads(get_token_name(token_address).data)

    f = io.StringIO()

    # ヘッダー行
    data_header = \
        'token_name,' + \
        'token_address,' + \
        'account_address,' + \
        'key_manager,' + \
        'balance,' + \
        'commitment,' + \
        'name,' + \
        'birth_date,' + \
        'postal_code,' + \
        'address,' + \
        'email\n'
    f.write(data_header)

    for holder in holders:
        # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
        holder_address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', holder["address"])
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + \
            holder["account_address"] + ',' + holder["key_manager"] + ','  + \
            str(holder["balance"]) + ',' + str(holder["commitment"]) + ',' + \
            holder["name"] + ',' + holder["birth_date"] + ',' + \
            holder["postal_code"] + ',' + holder_address + ',' + \
            holder["email"] + '\n'
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = f"attachment; filename={now.strftime('%Y%m%d%H%M%S')}share_holders_list.csv"
    return res


####################################################
# [株式]保有者リスト履歴
####################################################
@share.route('/holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def holders_csv_history(token_address):
    logger.info('share/holders_csv_history')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address):
        abort(404)

    return render_template(
        'share/holders_csv_history.html',
        token_address=token_address
    )


# 保有者リスト履歴（API）
@share.route('/get_holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def get_holders_csv_history(token_address):
    logger.info('share/get_holders_csv_history')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address):
        abort(404)

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    holder_lists = HolderList.query.filter(HolderList.token_address == token_address). \
        order_by(desc(HolderList.created)). \
        all()

    history = []
    for row in holder_lists:
        # utc→jst の変換
        created_jst = row.created.replace(tzinfo=timezone.utc).astimezone(JST)
        created_formatted = created_jst.strftime("%Y/%m/%d %H:%M:%S %z")
        file_name = created_jst.strftime("%Y%m%d%H%M%S") + 'share_holders_list.csv'
        history.append({
            'id': row.id,
            'token_address': row.token_address,
            'created': created_formatted,
            'file_name': file_name
        })

    return jsonify(history)


# 保有者リストCSVダウンロード
@share.route('/holders_csv_history_download', methods=['POST'])
@login_required
def holders_csv_history_download():
    logger.info('share/holders_csv_history_download')

    token_address = request.form.get('token_address')
    csv_id = request.form.get('csv_id')

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    holder_list = HolderList.query.filter(HolderList.id == csv_id, HolderList.token_address == token_address).first()
    if holder_list is None:
        abort(404)

    created = holder_list.created.replace(tzinfo=timezone.utc).astimezone(JST)
    res = make_response()
    res.data = holder_list.holder_list
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + created.strftime("%Y%m%d%H%M%S") \
                                         + 'share_holders_list.csv'
    return res


# 保有者リスト取得
@share.route('/get_holders/<string:token_address>', methods=['GET'])
@login_required
def get_holders(token_address):
    """
    保有者一覧取得
    :param token_address: トークンアドレス
    :return: トークンの保有者一覧
    """
    logger.info('share/get_holders')

    DEFAULT_VALUE = "--"

    token_owner = session['eth_account']
    issuer = Issuer.query.get(session['issuer_id'])

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=token_owner,
        template_id=Config.TEMPLATE_ID_SHARE
    )

    # DEXコントラクト接続
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as err:
        logger.error(f"Failed to get token attributes: {err}")
        tradable_exchange = Config.ZERO_ADDRESS
    dex_contract = ContractUtils.get_contract('IbetOTCExchange', tradable_exchange)

    # Transferイベントを検索
    # →　残高を保有している可能性のあるアドレスを抽出
    # →　保有者リストをユニークにする
    transfer_events = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address).all()

    holders_temp = [token_owner]  # 発行体アドレスをリストに追加
    for event in transfer_events:
        holders_temp.append(event.account_address_to)

    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    # 保有者情報を取得
    _holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        try:
            commitment = dex_contract.functions.commitmentOf(account_address, token_address).call()
        except Exception as err:
            logger.warning(f"Failed to get commitment: {err}")
            commitment = 0

        if balance > 0 or commitment > 0:  # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
            # アドレス種別判定
            if account_address == token_owner:
                address_type = AddressType.ISSUER.value
            elif account_address == tradable_exchange:
                address_type = AddressType.EXCHANGE.value
            else:
                address_type = AddressType.OTHERS.value

            # 保有者情報：デフォルト値（個人情報なし）
            _holder = {
                'account_address': account_address,
                'key_manager': DEFAULT_VALUE,
                'name': DEFAULT_VALUE,
                'postal_code': DEFAULT_VALUE,
                'email': DEFAULT_VALUE,
                'address': DEFAULT_VALUE,
                'birth_date': DEFAULT_VALUE,
                'balance': balance,
                'commitment': commitment,
                'address_type': address_type
            }

            if address_type == AddressType.ISSUER.value:  # 保有者が発行体の場合
                _holder["name"] = issuer.issuer_name or '--'
                _holders.append(_holder)
            else:  # 保有者が発行体以外の場合
                record = PersonalInfoModel.query. \
                    filter(PersonalInfoModel.account_address == account_address). \
                    filter(PersonalInfoModel.issuer_address == token_owner). \
                    first()

                if record is not None:
                    decrypted_personal_info = record.personal_info
                    # 住所の編集
                    prefecture = decrypted_personal_info["address"]["prefecture"]
                    city = decrypted_personal_info["address"]["city"]
                    address_1 = decrypted_personal_info["address"]["address1"]
                    address_2 = decrypted_personal_info["address"]["address2"]
                    if prefecture is not None and city is not None:
                        formatted_address = prefecture + city
                    else:
                        formatted_address = DEFAULT_VALUE
                    if address_1 is not None and address_1 != "":
                        formatted_address = formatted_address + "　" + address_1
                    if address_2 is not None and address_2 != "":
                        formatted_address = formatted_address + "　" + address_2

                    _holder = {
                        'account_address': account_address,
                        'key_manager': decrypted_personal_info["key_manager"],
                        'name': decrypted_personal_info["name"],
                        'postal_code': decrypted_personal_info["address"]["postal_code"],
                        'email': decrypted_personal_info["email"],
                        'address': formatted_address,
                        'birth_date': decrypted_personal_info["birth"],
                        'balance': balance,
                        'commitment': commitment,
                        'address_type': address_type
                    }

                _holders.append(_holder)

    return jsonify(_holders)


####################################################
# [株式]保有者移転
####################################################
@share.route('/transfer_ownership/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info('share/transfer_ownership')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'], Config.TEMPLATE_ID_SHARE)

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
                    'share/transfer_ownership.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )
            tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # NOTE: 保有者一覧が非同期で更新されるため、5秒待つ
            time.sleep(5)
            return redirect(url_for('.holders', token_address=token_address))
        else:
            flash_errors(form)
            form.from_address.data = account_address
            return render_template(
                'share/transfer_ownership.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        form.from_address.data = account_address
        form.to_address.data = ''
        form.amount.data = balance
        return render_template(
            'share/transfer_ownership.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


####################################################
# [株式]保有者詳細
####################################################
@share.route('/holder/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def holder(token_address, account_address):
    """保有者詳細取得

    :param token_address: トークンアドレス
    :param account_address: アカウントアドレス
    :return: 保有者詳細情報
    """
    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address) or not Web3.isAddress(account_address):
        abort(404)
    token_address = to_checksum_address(token_address)
    account_address = to_checksum_address(account_address)

    token_owner = session['eth_account']

    # トークンで指定した個人情報コントラクトのアドレスを取得
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=token_owner,
        template_id=Config.TEMPLATE_ID_SHARE
    )
    try:
        personal_info_address = TokenContract.functions.personalInfoAddress().call()
    except Exception as e:
        logger.exception(e)
        personal_info_address = Config.ZERO_ADDRESS

    # PersonalInfoコントラクト接続
    personal_info_contract = PersonalInfoContract(
        issuer_address=token_owner,
        custom_personal_info_address=personal_info_address
    )

    #########################
    # GET：参照
    #########################
    if request.method == "GET":
        logger.info('share/holder')
        personal_info = personal_info_contract.get_info(
            account_address=account_address,
            default_value="--"
        )
        return render_template(
            'share/holder.html',
            personal_info=personal_info,
            token_address=token_address,
            account_address=account_address
        )

    #########################
    # POST：個人情報更新
    #########################
    if request.method == "POST":
        if request.form.get('_method') == 'DELETE':  # 個人情報初期化
            logger.info('share/holder(DELETE)')
            try:
                personal_info_contract.modify_info(
                    account_address=account_address,
                    data={},
                )
                flash('個人情報の初期化に成功しました。', 'success')
            except EthRuntimeError:
                flash('個人情報の初期化に失敗しました。', 'error')

            personal_info = personal_info_contract.get_info(
                account_address=account_address,
                default_value="--"
            )

            return render_template(
                'share/holder.html',
                personal_info=personal_info,
                token_address=token_address,
                account_address=account_address
            )


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
