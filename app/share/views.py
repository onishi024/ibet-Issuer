"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""
import csv
import json
import re
import uuid
from datetime import (
    datetime,
    timezone,
    timedelta
)
import io
import time

from flask_wtf import FlaskForm as Form
from flask import (
    request,
    redirect,
    url_for,
    flash,
    make_response,
    render_template,
    abort,
    jsonify,
    session
)
from flask_login import (
    login_required,
    current_user
)
from sqlalchemy import (
    desc,
    or_
)
from eth_utils import to_checksum_address
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import ABIFunctionNotFound

from config import Config
from logging import getLogger
from app import db
from . import share
from app.share.forms import (
    IssueForm,
    SettingForm,
    AddSupplyForm,
    TransferOwnershipForm,
    TransferForm,
    AllotForm,
    BulkTransferUploadForm
)
from app.models import (
    Token,
    Transfer,
    IDXTransferApproval,
    AddressType,
    ApplyFor,
    Issuer,
    HolderList,
    PersonalInfoContract,
    BulkTransfer,
    BulkTransferUpload,
    PersonalInfo as PersonalInfoModel
)
from app.utils import (
    ContractUtils,
    TokenUtils
)
from app.exceptions import EthRuntimeError

logger = getLogger('api')
JST = timezone(timedelta(hours=+9), 'JST')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


####################################################
# 共通処理
####################################################
def flash_errors(form: Form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


####################################################
# トークン名取得
####################################################
@share.route('/get_token_name/<string:token_address>', methods=['GET'])
@login_required
def get_token_name(token_address):
    logger.info(f'[{current_user.login_id}] share/get_token_name')
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'], Config.TEMPLATE_ID_SHARE)
    token_name = TokenContract.functions.name().call()

    return jsonify(token_name)


####################################################
# 新規発行
####################################################
@share.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info(f'[{current_user.login_id}] share/issue')
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
            arguments = [
                form.name.data,
                form.symbol.data,
                form.issuePrice.data,
                form.totalSupply.data,
                int(form.dividends.data * 100),
                form.dividendRecordDate.data,
                form.dividendPaymentDate.data,
                form.cancellationDate.data,
                form.principalValue.data
            ]
            _, bytecode, bytecode_runtime = ContractUtils.get_contract_info('IbetShare')
            contract_address, abi, tx_hash = ContractUtils.deploy_contract(
                contract_name='IbetShare',
                args=arguments,
                deployer=session["eth_account"]
            )

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

            # トークンが正常にデプロイされた後に各種設定値の登録処理を実行する
            if contract_address is not None:
                TokenContract = web3.eth.contract(address=contract_address, abi=abi)

                # 補足情報の登録処理
                if form.memo.data != '':
                    tx = TokenContract.functions.setMemo(form.memo.data). \
                        buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 譲渡制限の登録処理(bool型に変換)
                bool_transferable = form.transferable.data != 'False'
                if bool_transferable is True:
                    tx = TokenContract.functions.setTransferable(bool_transferable). \
                        buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 移転承諾要否の登録処理(bool型に変換)
                bool_transferApprovalRequired = form.transferApprovalRequired.data != 'False'
                if bool_transferApprovalRequired is True:
                    tx = TokenContract.functions.setTransferApprovalRequired(bool_transferApprovalRequired). \
                        buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 関連URLの登録処理
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

                # 問い合わせ先の登録処理
                if form.contact_information.data != '':
                    tx = TokenContract.functions.setContactInformation(form.contact_information.data). \
                        buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # プライバシーポリシーの登録処理
                if form.privacy_policy.data != '':
                    tx = TokenContract.functions.setPrivacyPolicy(form.privacy_policy.data). \
                        buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # DEXアドレスの登録処理
                tx = TokenContract.functions.setTradableExchange(to_checksum_address(form.tradableExchange.data)). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 個人情報コントラクトの登録処理
                tx = TokenContract.functions.setPersonalInfoAddress(to_checksum_address(form.personalInfoAddress.data)). \
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
# 発行済一覧
####################################################
@share.route('/list', methods=['GET'])
@login_required
def list():
    logger.info(f'[{current_user.login_id}] share/list')

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
# 設定内容修正
####################################################
@share.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info(f'[{current_user.login_id}] share/setting')

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
    principalValue = TokenContract.functions.principalValue().call()
    dividends, dividendRecordDate, dividendPaymentDate = TokenContract.functions.dividendInformation().call()
    dividends = dividends * 0.01
    cancellationDate = TokenContract.functions.cancellationDate().call()
    transferable = str(TokenContract.functions.transferable().call())
    transferApprovalRequired = str(TokenContract.functions.transferApprovalRequired().call())
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

            # １口あたりの元本額変更
            if form.principalValue.data is None:
                form.principalValue.data = 0
            if form.principalValue.data != principalValue:
                tx = TokenContract.functions.setPrincipalValue(form.principalValue.data). \
                    buildTransaction({'from': session["eth_account"], 'gas': Config.TX_GAS_LIMIT})
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

            # 移転承諾要否変更
            if form.transferApprovalRequired.data != transferApprovalRequired:
                bool_transferApprovalRequired = True
                if form.transferApprovalRequired.data == 'False':
                    bool_transferApprovalRequired = False
                tx = TokenContract.functions.setTransferApprovalRequired(bool_transferApprovalRequired). \
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
        form.principalValue.data = principalValue
        form.dividends.data = dividends
        form.dividendRecordDate.data = dividendRecordDate
        form.dividendPaymentDate.data = dividendPaymentDate
        form.cancellationDate.data = cancellationDate
        form.transferable.data = transferable
        form.transferApprovalRequired.data = transferApprovalRequired
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
# 公開
####################################################
@share.route('/release', methods=['POST'])
@login_required
def release():
    logger.info(f'[{current_user.login_id}] share/release')
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
# 募集申込開始/停止
####################################################
@share.route('/start_offering', methods=['POST'])
@login_required
def start_offering():
    logger.info(f'[{current_user.login_id}] share/start_offering')
    token_address = request.form.get('token_address')
    _set_offering_status(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@share.route('/stop_offering', methods=['POST'])
@login_required
def stop_offering():
    logger.info(f'[{current_user.login_id}] share/stop_offering')
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
# 有効化/無効化
####################################################
@share.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info(f'[{current_user.login_id}] share/valid')
    token_address = request.form.get('token_address')
    _set_validity(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@share.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info(f'[{current_user.login_id}] share/invalid')
    token_address = request.form.get('token_address')
    _set_validity(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def _set_validity(token_address, isvalid):
    """
    取扱ステータス変更
    :param token_address: トークンアドレス
    :param isvalid: 変更後ステータス
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
# 追加発行
####################################################
@share.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info(f'[{current_user.login_id}] share/add_supply')

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
# トークン追跡
####################################################
@share.route('/token/track/<string:token_address>', methods=['GET'])
@login_required
def token_tracker(token_address):
    logger.info(f'[{current_user.login_id}] share/token_tracker')

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
            # utc→jst の変換
            block_timestamp = row.block_timestamp.replace(tzinfo=timezone.utc).astimezone(JST). \
                strftime("%Y/%m/%d %H:%M:%S %z")
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

    return render_template(
        'share/token_tracker.html',
        token_address=token_address,
        track=track
    )


# トークン追跡（CSVダウンロード）
@share.route('/token/tracks_csv_download', methods=['POST'])
@login_required
def token_tracker_csv():
    logger.info(f'[{current_user.login_id}] share/token_tracker_csv')

    token_address = request.form.get('token_address')

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

    f = io.StringIO()

    # ヘッダー行
    data_header = \
        'transaction_hash,' + \
        'token_address,' + \
        'account_address_from,' + \
        'account_address_to,' + \
        'transfer_amount,' + \
        'block_timestamp\n'
    f.write(data_header)

    for track in tracks:
        # utc→jst の変換
        block_timestamp = track.block_timestamp.replace(tzinfo=timezone.utc).astimezone(JST). \
            strftime("%Y/%m/%d %H:%M:%S %z")
        # データ行
        data_row = \
            track.transaction_hash + ',' + \
            track.token_address + ',' + \
            track.account_address_from + ',' + \
            track.account_address_to + ',' + \
            str(track.transfer_amount) + ',' + \
            block_timestamp + '\n'
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = f"attachment; filename={now.strftime('%Y%m%d%H%M%S')}_share_tracks.csv"

    return res


####################################################
# トークン移転承諾
####################################################
@share.route("/token/transfer_approvals/<string:token_address>", methods=["GET"])
@login_required
def list_all_transfer_approvals(token_address):
    logger.info(f"[{current_user.login_id}] share/list_all_transfer_approvals")

    # Validation
    if not Web3.isAddress(token_address):
        abort(404)

    # Check if the token is issued by the issuer
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session["eth_account"].lower()). \
        first()
    if token is None:
        abort(404)

    _transfer_approvals = IDXTransferApproval.query.\
        filter(IDXTransferApproval.token_address == token_address). \
        order_by(desc(IDXTransferApproval.application_id)). \
        all()

    resp_transfer_approvals = []
    for _transfer_approval in _transfer_approvals:
        try:
            _application_datetime = _transfer_approval.application_datetime
            _application_blocktimestamp = _transfer_approval.application_blocktimestamp
            _approval_datetime = _transfer_approval.approval_datetime
            _approval_blocktimestamp = _transfer_approval.approval_blocktimestamp
            if _application_datetime is not None:
                _application_datetime = _application_datetime.\
                    replace(tzinfo=timezone.utc).astimezone(JST).strftime("%Y/%m/%d %H:%M:%S %z")
            if _application_blocktimestamp is not None:
                _application_blocktimestamp = _application_blocktimestamp. \
                    replace(tzinfo=timezone.utc).astimezone(JST).strftime("%Y/%m/%d %H:%M:%S %z")
            if _approval_datetime is not None:
                _approval_datetime = _approval_datetime. \
                    replace(tzinfo=timezone.utc).astimezone(JST).strftime("%Y/%m/%d %H:%M:%S %z")
            if _approval_blocktimestamp is not None:
                _approval_blocktimestamp = _approval_blocktimestamp. \
                    replace(tzinfo=timezone.utc).astimezone(JST).strftime("%Y/%m/%d %H:%M:%S %z")
            resp_transfer_approvals.append({
                "application_id": _transfer_approval.application_id,
                "from_address": _transfer_approval.from_address,
                "to_address": _transfer_approval.to_address,
                "value": _transfer_approval.value,
                "application_datetime": _application_datetime,
                "application_blocktimestamp": _application_blocktimestamp,
                "approval_datetime": _approval_datetime,
                "approval_blocktimestamp": _approval_blocktimestamp,
                "cancelled": _transfer_approval.cancelled
            })
        except Exception as e:
            logger.exception(e)

    return render_template(
        'share/transfer_approvals.html',
        token_address=token_address,
        transfer_approvals=resp_transfer_approvals
    )


####################################################
# 募集申込一覧
####################################################
# 申込一覧画面
@share.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info(f'[{current_user.login_id}] share/applications')
    return render_template(
        'share/applications.html',
        token_address=token_address,
    )


# 申込者リストCSVダウンロード
@share.route('/applications_csv_download', methods=['POST'])
@login_required
def applications_csv_download():
    logger.info(f'[{current_user.login_id}] share/applications_csv_download')

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

    _applications = []
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
        _applications.append(application)

    return jsonify(_applications)


####################################################
# 割当登録
####################################################
@share.route('/allot/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def allot(token_address, account_address):
    """
    募集申込割当登録

    :param token_address: トークンアドレス
    :param account_address: 割当対象のアカウントアドレス
    """
    logger.info(f'[{current_user.login_id}] share/allot')

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
# 権利移転（募集申込）
####################################################
@share.route('/transfer_allotment/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_allotment(token_address, account_address):
    """
    募集申込割当登録

    :param token_address: トークンアドレス
    :param account_address: 移転先のアカウントアドレス
    """
    logger.info(f'[{current_user.login_id}] share/transfer_allotment')

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
# 保有者一覧
####################################################

# （画面）保有者一覧
@share.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info(f'[{current_user.login_id}] share/holders')

    return render_template(
        'share/holders.html',
        token_address=token_address
    )


# （画面）保有者リスト履歴
@share.route('/holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def holders_csv_history(token_address):
    logger.info(f'[{current_user.login_id}] share/holders_csv_history')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address):
        abort(404)

    return render_template(
        'share/holders_csv_history.html',
        token_address=token_address
    )


# （画面）保有者リスト履歴
@share.route('/get_holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def get_holders_csv_history(token_address):
    logger.info(f'[{current_user.login_id}] share/get_holders_csv_history')

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
@share.route('/holders_csv_download', methods=['POST'])
@login_required
def holders_csv_download():
    logger.info(f'[{current_user.login_id}] share/holders_csv_download')

    token_address = request.form.get('token_address')
    _holders = get_holders(token_address)["data"]
    token_name = json.loads(get_token_name(token_address).data)

    f = io.StringIO()

    # ヘッダー行
    data_header = f"token_name," \
                  f"token_address," \
                  f"account_address," \
                  f"key_manager," \
                  f"balance," \
                  f"name," \
                  f"birth_date," \
                  f"postal_code," \
                  f"address," \
                  f"email" \
                  f"\n"
    f.write(data_header)

    for _holder in _holders:
        # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
        try:
            holder_address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', _holder["address"])
        except TypeError:
            holder_address = ""
        # データ行
        data_row = f"{token_name}," \
                   f"{token_address}," \
                   f"{_holder['account_address']}," \
                   f"{_holder['key_manager']}," \
                   f"{str(_holder['balance'])}," \
                   f"{_holder['name']}," \
                   f"{_holder['birth_date']}," \
                   f"{_holder['postal_code']}," \
                   f"{holder_address}," \
                   f"{_holder['email']}" \
                   f"\n"
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = f"attachment; filename={now.strftime('%Y%m%d%H%M%S')}share_holders_list.csv"
    return res


# 保有者リストCSV履歴ダウンロード
@share.route('/holders_csv_history_download', methods=['POST'])
@login_required
def holders_csv_history_download():
    logger.info(f'[{current_user.login_id}] share/holders_csv_history_download')

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
    """保有者一覧取得

    :param token_address: トークンアドレス
    :return: トークンの保有者一覧
    """
    logger.info(f'[{current_user.login_id}] share/get_holders')

    DEFAULT_VALUE = "--"

    # query parameters
    draw = int(request.args.get("draw")) if request.args.get("draw") else None  # record the number of operations
    start = int(request.args.get("start")) if request.args.get("start") else None  # start position
    length = int(request.args.get("length")) if request.args.get("length") else None  # length of each page
    search_address = request.args.get("search[value]")  # search keyword

    token_owner = session['eth_account']
    issuer = Issuer.query.get(session['issuer_id'])

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

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

    # Transferイベントを検索
    # →　残高を保有している可能性のあるアドレスを抽出
    # →　保有者リストをユニークにする
    query = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address)
    if search_address:
        transfer_events = query.filter(or_(
            Transfer.account_address_from.like(f"%{search_address}%"),
            Transfer.account_address_to.like(f"%{search_address}%"))
        ).all()
    else:
        transfer_events = query.all()

    holders_temp = [token_owner]  # 発行体アドレスをリストに追加
    for event in transfer_events:
        holders_temp.append(event.account_address_to)

    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            if search_address is None:
                holders_uniq.append(x)
            elif search_address in x:
                holders_uniq.append(x)

    # 保有者情報を取得
    _holders = []
    cursor = -1  # 開始位置
    count = 0  # 取得レコード
    for account_address in holders_uniq:
        cursor += 1
        if ((start is not None and cursor >= start) and (length is not None and count < length)) or \
                (start is None and length is None):
            count += 1

            # 保有残高取得
            try:
                balance = TokenContract.functions.balanceOf(account_address).call()
            except ABIFunctionNotFound:
                balance = 0

            # 移転承諾待ち数量取得
            try:
                pending_transfer = TokenContract.functions.pendingTransfer(account_address).call()
            except ABIFunctionNotFound:
                pending_transfer = 0

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
                'balance': balance + pending_transfer,
                'address_type': address_type
            }

            if address_type == AddressType.ISSUER.value:  # 保有者が発行体の場合
                _holder["name"] = issuer.issuer_name or DEFAULT_VALUE
                _holders.append(_holder)
            else:  # 保有者が発行体以外の場合
                record = PersonalInfoModel.query. \
                    filter(PersonalInfoModel.account_address == account_address). \
                    filter(PersonalInfoModel.issuer_address == token_owner). \
                    first()

                if record is not None:
                    decrypted_personal_info = record.personal_info
                    key_manager = decrypted_personal_info.get("key_manager") or DEFAULT_VALUE
                    name = decrypted_personal_info.get("name") or DEFAULT_VALUE
                    postal_code = decrypted_personal_info.get("postal_code") or DEFAULT_VALUE
                    address = decrypted_personal_info.get("address") or DEFAULT_VALUE
                    email = decrypted_personal_info.get("email") or DEFAULT_VALUE
                    birth_date = decrypted_personal_info.get("birth") or DEFAULT_VALUE
                    _holder = {
                        'account_address': account_address,
                        'key_manager': key_manager,
                        'name': name,
                        'postal_code': postal_code,
                        'address': address,
                        'email': email,
                        'birth_date': birth_date,
                        'balance': balance + pending_transfer,
                        'address_type': address_type
                    }

                _holders.append(_holder)
        elif length is not None and count >= length:
            break

    records_total = len(holders_uniq)
    records_filtered = records_total

    res_body = {
        "draw": draw,
        "recordsTotal": records_total,
        "recordsFiltered": records_filtered,
        "data": _holders
    }

    return res_body


####################################################
# 保有者移転
####################################################
@share.route('/transfer_ownership/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info(f'[{current_user.login_id}] share/transfer_ownership')

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
# 保有者詳細
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
        logger.info(f'[{current_user.login_id}] share/holder')
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
            logger.info(f'[{current_user.login_id}] share/holder(DELETE)')
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


#################################################
# 一括強制移転
#################################################

# 一括強制移転CSVアップロード
@share.route('/bulk_transfer', methods=['GET', 'POST'])
@login_required
def bulk_transfer():
    form = BulkTransferUploadForm()

    #########################
    # GET：アップロード画面参照
    #########################
    if request.method == "GET":
        logger.info(f"[{current_user.login_id}] share/bulk_transfer(GET)")
        return render_template("share/bulk_transfer.html", form=form)

    #########################
    # POST：ファイルアップロード
    #########################
    if request.method == "POST":
        logger.info(f"[{current_user.login_id}] share/bulk_transfer(POST)")

        # Formバリデート
        if form.validate() is False:
            flash_errors(form)
            return render_template("share/bulk_transfer.html", form=form)

        send_data = request.files["transfer_csv"]

        # CSVファイル読み込み
        _transfer_list = []
        record_count = 0
        try:
            stream = io.StringIO(send_data.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            for row in csv_input:
                _transfer_list.append(row)
                record_count += 1
        except Exception as err:
            logger.error(f"Failed to upload file: {err}")
            flash("CSVアップロードでエラーが発生しました。", "error")
            return render_template("share/bulk_transfer.html", form=form)

        # レコード存在チェック
        if record_count == 0:
            flash("レコードが0件のファイルはアップロードできません。", "error")
            return render_template("share/bulk_transfer.html", form=form)

        # アップロードIDを生成（UUID4）
        upload_id = str(uuid.uuid4())

        token_address_0 = None
        for i, row in enumerate(_transfer_list):
            # <CHK>ファイルフォーマットチェック
            try:
                token_address = row[0]
                from_address = row[1]
                to_address = row[2]
                transfer_amount = row[3]
            except IndexError:
                flash("ファイルフォーマットが正しくありません。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # <CHK>アドレスフォーマットチェック（token_address）
            if not Web3.isAddress(token_address):
                flash(f"{i + 1}行目に無効なトークンアドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # <CHK>全てのトークンアドレスが同一のものであることのチェック
            if i == 0:
                token_address_0 = token_address
            if token_address_0 != token_address:
                flash(f"ファイル内に異なるトークンアドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # <CHK>発行体が管理するトークンであることをチェック
            token = Token.query. \
                filter(Token.token_address == token_address). \
                filter(Token.admin_address == session['eth_account'].lower()). \
                filter(Token.template_id == Config.TEMPLATE_ID_SHARE). \
                first()
            if token is None:
                flash(f"ファイル内に未発行のトークンアドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # <CHK>アドレスフォーマットチェック（from_address）
            if not Web3.isAddress(from_address):
                flash(f"{i + 1}行目に無効な移転元アドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # <CHK>アドレスフォーマットチェック（to_address）
            if not Web3.isAddress(to_address):
                flash(f"{i + 1}行目に無効な移転先アドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # <CHK>移転数量のフォーマットチェック
            if not transfer_amount.isdecimal():
                flash(f"{i + 1}行目に無効な移転数量が含まれています。", "error")
                db.session.rollback()
                return render_template("share/bulk_transfer.html", form=form)

            # DB登録処理（一括強制移転）
            _bulk_transfer = BulkTransfer()
            _bulk_transfer.eth_account = session['eth_account']
            _bulk_transfer.upload_id = upload_id
            _bulk_transfer.token_address = token_address
            _bulk_transfer.template_id = Config.TEMPLATE_ID_SHARE
            _bulk_transfer.from_address = from_address
            _bulk_transfer.to_address = to_address
            _bulk_transfer.amount = transfer_amount
            _bulk_transfer.approved = False
            _bulk_transfer.status = 0
            db.session.add(_bulk_transfer)

        # トークン名称を取得
        token_name = ""
        try:
            TokenContract = TokenUtils.get_contract(token_address_0, session['eth_account'])
            token_name = TokenContract.functions.name().call()
        except Exception as err:
            logger.warning(f"Failed to get token name: {err}")

        # DB登録処理（一括強制移転アップロード）
        _bulk_transfer_upload = BulkTransferUpload()
        _bulk_transfer_upload.upload_id = upload_id
        _bulk_transfer_upload.eth_account = session['eth_account']
        _bulk_transfer_upload.token_address = token_address_0
        _bulk_transfer_upload.token_name = token_name
        _bulk_transfer_upload.template_id = Config.TEMPLATE_ID_SHARE
        _bulk_transfer_upload.approved = False
        db.session.add(_bulk_transfer_upload)

        db.session.commit()
        flash("ファイルアップロードが成功しました。", "success")
        return redirect(url_for('.bulk_transfer'))


# 一括強制移転サンプルCSVダウンロード
@share.route('/bulk_transfer/sample', methods=['POST'])
@login_required
def bulk_transfer_sample():
    logger.info(f"[{current_user.login_id}] share/bulk_transfer_sample")

    f = io.StringIO()

    # サンプルデータ
    # トークンアドレス, 移転元アドレス, 移転先アドレス, 移転数量
    data_row = "0xD44a231af1C48105764D7298Bc694696DAb54179,0x0b3c7F97383bCFf942E6b1038a47B9AA5377A252,0xF37aF18966609eCaDe3E4D1831996853c637cfF3,10\n" \
               "0xD44a231af1C48105764D7298Bc694696DAb54179,0xC362102bC5bbA9fBd0F2f5d397f3644Aa32b3bA8,0xF37aF18966609eCaDe3E4D1831996853c637cfF3,20"

    f.write(data_row)

    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + 'transfer_sample.csv'
    return res


# 一括強制移転CSVアップロード履歴（API）
@share.route('/bulk_transfer_history', methods=['GET'])
@login_required
def bulk_transfer_history():
    logger.info(f'[{current_user.login_id}] share/bulk_transfer_history')

    records = BulkTransferUpload.query. \
        filter(BulkTransferUpload.eth_account == session["eth_account"]). \
        filter(BulkTransferUpload.template_id == Config.TEMPLATE_ID_SHARE). \
        order_by(desc(BulkTransferUpload.created)). \
        all()

    upload_list = []
    for record in records:
        # utc→jst の変換
        created_jst = record.created.replace(tzinfo=timezone.utc).astimezone(JST)
        created_formatted = created_jst.strftime("%Y/%m/%d %H:%M:%S %z")
        upload_list.append({
            "upload_id": record.upload_id,
            "token_address": record.token_address,
            "token_name": record.token_name,
            "approved": record.approved,
            "created": created_formatted
        })

    return jsonify(upload_list)


# 一括強制移転同意
@share.route('/bulk_transfer_approval/<string:upload_id>', methods=['GET', 'POST'])
@login_required
def bulk_transfer_approval(upload_id):

    #########################
    # GET：移転指示データ参照
    #########################
    if request.method == "GET":
        logger.info(f"[{current_user.login_id}] share/bulk_transfer_approval(GET)")

        # 移転指示明細データを取得
        bulk_transfer_records = BulkTransfer.query. \
            filter(BulkTransfer.eth_account == session["eth_account"]). \
            filter(BulkTransfer.upload_id == upload_id).\
            order_by(desc(BulkTransfer.created)).\
            all()

        transfer_list = []
        for record in bulk_transfer_records:
            transfer_list.append({
                'token_address': record.token_address,
                'from_address': record.from_address,
                'to_address': record.to_address,
                'amount': record.amount,
                'status': record.status,
            })

        # 移転アップロード情報を取得
        bulk_transfer_upload_record = BulkTransferUpload.query. \
            filter(BulkTransferUpload.eth_account == session["eth_account"]). \
            filter(BulkTransferUpload.upload_id == upload_id). \
            first()
        if bulk_transfer_upload_record is None:
            abort(404)
        approved = bulk_transfer_upload_record.approved

        return render_template(
            "share/bulk_transfer_approval.html",
            upload_id=upload_id,
            approved=approved,
            transfer_list=transfer_list
        )

    #########################
    # POST：移転指示データ承認
    #########################
    if request.method == "POST":
        logger.info(f'[{current_user.login_id}] share/bulk_transfer_approval(POST)')

        upload_id = request.form.get("upload_id")

        # 移転指示明細データの承認ステータスを承認済に変更する
        bulk_transfer_records = BulkTransfer.query. \
            filter(BulkTransfer.eth_account == session["eth_account"]). \
            filter(BulkTransfer.upload_id == upload_id). \
            all()
        for _record in bulk_transfer_records:
            _record.approved = True
            db.session.merge(_record)

        # 移転アップロードの承認ステータスを承認済に変更する
        bulk_transfer_upload_record = BulkTransferUpload.query. \
            filter(BulkTransferUpload.eth_account == session["eth_account"]). \
            filter(BulkTransferUpload.upload_id == upload_id). \
            first()
        if bulk_transfer_upload_record is not None:
            bulk_transfer_upload_record.approved = True
            db.session.merge(bulk_transfer_upload_record)

        # 更新内容をコミット
        db.session.commit()

        flash('移転処理を開始しました。', 'success')
        return redirect(url_for('.bulk_transfer_approval', upload_id=upload_id))


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
