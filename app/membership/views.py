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
import io
import re
import time
import uuid
from datetime import datetime, timezone, timedelta

from flask_wtf import FlaskForm as Form
from flask import request, redirect, url_for, flash, make_response, render_template, abort, jsonify, session
from flask_login import login_required, current_user
from sqlalchemy import func, desc

from app import db
from app.models import Token, Order, Agreement, AgreementStatus, AddressType, ApplyFor, Transfer, Issuer, HolderList, \
    PersonalInfoContract, BulkTransfer, BulkTransferUpload
from app.models import PersonalInfo as PersonalInfoModel
from app.utils import ContractUtils, TokenUtils
from app.exceptions import EthRuntimeError
from config import Config
from . import membership
from .forms import TransferForm, TransferOwnershipForm, SettingForm, SellForm, IssueForm, CancelOrderForm, \
    AddSupplyForm, BulkTransferUploadForm

from web3 import Web3
from eth_utils import to_checksum_address
from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

from logging import getLogger

logger = getLogger('api')

JST = timezone(timedelta(hours=+9), 'JST')


####################################################
# 共通処理
####################################################

# 共通処理：エラー表示
def flash_errors(form: Form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


# 共通処理：トークン移転（強制移転）
def transfer_token(token_contract, from_address, to_address, amount):
    tx = token_contract.functions.transferFrom(from_address, to_address, amount). \
        buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
    tx_hash, txn_receipt = ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
    return tx_hash


####################################################
# 発行済一覧
####################################################
@membership.route('/list', methods=['GET'])
@login_required
def list():
    logger.info(f'[{current_user.login_id}] membership/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_MEMBERSHIP,
        # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
        admin_address=session['eth_account'].lower()
    ).all()

    token_list = []
    for row in tokens:
        try:
            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
                status = '--'
                totalSupply = '--'
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
                totalSupply = TokenContract.functions.totalSupply().call()

            # 作成日時（JST）
            created = datetime.fromtimestamp(row.created.timestamp(), JST).strftime("%Y/%m/%d %H:%M:%S %z")

            token_list.append({
                'name': name,
                'symbol': symbol,
                'created': created,
                'tx_hash': row.tx_hash,
                'token_address': row.token_address,
                'totalSupply': totalSupply,
                'status': status
            })
        except Exception as e:
            logger.error(e)
            pass

    return render_template('membership/list.html', tokens=token_list)


####################################################
# トークン追跡
####################################################
@membership.route('/token/track/<string:token_address>', methods=['GET'])
@login_required
def token_tracker(token_address):
    logger.info(f'[{current_user.login_id}] membership/token_tracker')

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
        'membership/token_tracker.html',
        token_address=token_address,
        track=track
    )


# トークン追跡（CSVダウンロード）
@membership.route('/token/tracks_csv_download', methods=['POST'])
@login_required
def token_tracker_csv():
    logger.info(f'[{current_user.login_id}] membership/token_tracker_csv')

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
    res.headers['Content-Disposition'] = f"attachment; filename={now.strftime('%Y%m%d%H%M%S')}_membership_tracks.csv"

    return res


####################################################
# 募集申込一覧
####################################################
# 申込一覧画面
@membership.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info(f'[{current_user.login_id}] membership/applications')
    return render_template(
        'membership/applications.html',
        token_address=token_address,
    )


# 申込者リストCSVダウンロード
@membership.route('/applications_csv_download', methods=['POST'])
@login_required
def applications_csv_download():
    logger.info(f'[{current_user.login_id}] membership/applications_csv_download')

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
        'code\n'
    f.write(data_header)

    for item in application:
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + item["account_address"] + ',' + \
            item["account_name"] + ',' + item["account_email_address"] + ',' + item["data"] + '\n'
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = \
        'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") + 'membership_applications_list.csv'
    return res


# 申込一覧取得
@membership.route('/get_applications/<string:token_address>', methods=['GET'])
@login_required
def get_applications(token_address):
    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=session['eth_account'],
        template_id=Config.TEMPLATE_ID_MEMBERSHIP
    )

    # PersonalInfoコントラクト接続
    personal_info_contract = PersonalInfoContract(
        issuer_address=session['eth_account']
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
        data = TokenContract.functions.applications(account_address).call()
        _application = {
            'account_address': account_address,
            'account_name': personal_info['name'],
            'account_email_address': personal_info['email'],
            'data': data
        }
        _applications.append(_application)

    return jsonify(_applications)


####################################################
# 割当（募集申込）
####################################################
@membership.route('/allocate/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def allocate(token_address, account_address):
    logger.info(f'[{current_user.login_id}] membership/allocate')

    # アドレスのフォーマットチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    form = TransferForm()
    form.token_address.data = token_address
    form.to_address.data = account_address
    if request.method == 'POST':
        if form.validate():
            # 残高チェック
            amount = int(form.amount.data)
            balance = TokenContract.functions. \
                balanceOf(to_checksum_address(session['eth_account'])).call()
            if amount > balance:
                flash('移転数量が残高を超えています。', 'error')
                return render_template(
                    'membership/allocate.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            # 割当処理（発行体アドレス→指定アドレス）
            from_address = session['eth_account']
            to_address = to_checksum_address(account_address)
            transfer_token(TokenContract, from_address, to_address, amount)
            # NOTE: 募集申込一覧が非同期で更新されるため、5秒待つ
            time.sleep(5)
            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.applications', token_address=token_address))
        else:
            flash_errors(form)
            return render_template(
                'membership/allocate.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        return render_template(
            'membership/allocate.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


####################################################
# 保有者一覧
####################################################
@membership.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info(f'[{current_user.login_id}] membership/holders')
    return render_template(
        'membership/holders.html',
        token_address=token_address
    )


# 保有者リストCSVダウンロード
@membership.route('/holders_csv_download', methods=['POST'])
@login_required
def holders_csv_download():
    logger.info(f'[{current_user.login_id}] membership/holders_csv_download')

    token_address = request.form.get('token_address')
    _holders = json.loads(get_holders(token_address).data)
    token_name = json.loads(get_token_name(token_address).data)

    f = io.StringIO()

    # ヘッダー行
    data_header = f"token_name," \
                  f"token_address," \
                  f"account_address," \
                  f"balance," \
                  f"commitment," \
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
                   f"{str(_holder['balance'])}," \
                   f"{str(_holder['commitment'])}," \
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
    res.headers['Content-Disposition'] = 'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") \
                                         + 'membership_holders_list.csv'
    return res


@membership.route('/get_holders/<string:token_address>', methods=['GET'])
@login_required
def get_holders(token_address):
    """
    保有者一覧取得
    :param token_address: トークンアドレス
    :return: トークンの保有者一覧
    """
    logger.info(f'[{current_user.login_id}] membership/get_holders')

    DEFAULT_VALUE = "--"

    token_owner = session['eth_account']
    issuer = Issuer.query.get(session['issuer_id'])

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=token_owner,
        template_id=Config.TEMPLATE_ID_MEMBERSHIP
    )

    # DEXコントラクト接続
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as err:
        logger.error(f"Failed to get token attributes: {err}")
        tradable_exchange = Config.ZERO_ADDRESS
    dex_contract = ContractUtils.get_contract('IbetMembershipExchange', tradable_exchange)

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

    # 保有者情報抽出
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
                        'balance': balance,
                        'commitment': commitment,
                        'address_type': address_type
                    }

                _holders.append(_holder)

    return jsonify(_holders)


@membership.route('/get_token_name/<string:token_address>', methods=['GET'])
@login_required
def get_token_name(token_address):
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])
    token_name = TokenContract.functions.name().call()

    return jsonify(token_name)


####################################################
# 保有者リスト履歴
####################################################
@membership.route('/holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def holders_csv_history(token_address):
    logger.info(f'[{current_user.login_id}] membership/holders_csv_history')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address):
        abort(404)

    return render_template(
        'membership/holders_csv_history.html',
        token_address=token_address
    )


# 保有者リスト履歴（API）
@membership.route('/get_holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def get_holders_csv_history(token_address):
    logger.info(f'[{current_user.login_id}] membership/get_holders_csv_history')

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
        file_name = created_jst.strftime("%Y%m%d%H%M%S") + 'membership_holders_list.csv'
        history.append({
            'id': row.id,
            'token_address': row.token_address,
            'created': created_formatted,
            'file_name': file_name
        })

    return jsonify(history)


# 保有者リストCSVダウンロード
@membership.route('/holders_csv_history_download', methods=['POST'])
@login_required
def holders_csv_history_download():
    logger.info(f'[{current_user.login_id}] membership/holders_csv_history_download')

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
                                         + 'membership_holders_list.csv'
    return res


####################################################
# 保有者移転
####################################################
@membership.route('/transfer_ownership/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info(f'[{current_user.login_id}] membership/transfer_ownership')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

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
                    'membership/transfer_ownership.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            txid = transfer_token(TokenContract, from_address, to_address, amount)
            web3.eth.waitForTransactionReceipt(txid)
            # NOTE: 保有者一覧が非同期で更新されるため、5秒待つ
            time.sleep(5)
            return redirect(url_for('.holders', token_address=token_address))
        else:
            flash_errors(form)
            form.from_address.data = account_address
            return render_template(
                'membership/transfer_ownership.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        form.from_address.data = account_address
        form.to_address.data = ''
        form.amount.data = balance
        return render_template(
            'membership/transfer_ownership.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


####################################################
# 保有者詳細
####################################################
@membership.route('/holder/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def holder(token_address, account_address):
    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address) or not Web3.isAddress(account_address):
        abort(404)
    token_address = to_checksum_address(token_address)
    account_address = to_checksum_address(account_address)

    token_owner = session['eth_account']

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    # PersonalInfoコントラクト接続
    personal_info_contract = PersonalInfoContract(
        issuer_address=token_owner
    )

    #########################
    # GET：参照
    #########################
    if request.method == "GET":
        logger.info(f'[{current_user.login_id}] membership/holder(GET)')
        personal_info = personal_info_contract.get_info(
            account_address=account_address,
            default_value="--"
        )
        return render_template(
            'membership/holder.html',
            personal_info=personal_info,
            token_address=token_address,
            account_address=account_address
        )

    #########################
    # POST：個人情報更新
    #########################
    if request.method == "POST":
        if request.form.get('_method') == 'DELETE':  # 個人情報初期化
            logger.info(f'[{current_user.login_id}] membership/holder(DELETE)')
            try:
                personal_info_contract.modify_info(
                    account_address=account_address,
                    data={}
                )
                flash('個人情報の初期化に成功しました。', 'success')
            except EthRuntimeError:
                flash('個人情報の初期化に失敗しました。', 'error')

            personal_info = personal_info_contract.get_info(
                account_address=account_address,
                default_value="--"
            )

            return render_template(
                'membership/holder.html',
                personal_info=personal_info,
                token_address=token_address,
                account_address=account_address
            )


####################################################
# 設定内容修正
####################################################
@membership.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info(f'[{current_user.login_id}] membership.setting')

    # 指定したトークンが存在しない場合、エラーを返す
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
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
    expirationDate = TokenContract.functions.expirationDate().call()
    memo = TokenContract.functions.memo().call()
    transferable = str(TokenContract.functions.transferable().call())
    tradableExchange = TokenContract.functions.tradableExchange().call()
    status = TokenContract.functions.status().call()
    image_1 = TokenContract.functions.getImageURL(0).call()
    image_2 = TokenContract.functions.getImageURL(1).call()
    image_3 = TokenContract.functions.getImageURL(2).call()
    contact_information = TokenContract.functions.contactInformation().call()
    privacy_policy = TokenContract.functions.privacyPolicy().call()
    initial_offering_status = TokenContract.functions.initialOfferingStatus().call()

    # TokenList登録状態取得
    issuer = Issuer.query.get(session['issuer_id'])
    list_contract_address = issuer.token_list_contract_address
    ListContract = ContractUtils.get_contract('TokenList', list_contract_address)
    token_struct = ListContract.functions.getTokenByAddress(token_address).call()
    isRelease = False
    if token_struct[0] == token_address:
        isRelease = True

    form = SettingForm()
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
                    'membership/setting.html',
                    form=form, token_address=token_address,
                    isRelease=isRelease, status=status, token_name=name
                )
            # トークン詳細変更
            if form.details.data != details:
                tx = TokenContract.functions.setDetails(form.details.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # 特典詳細変更
            if form.return_details.data != return_details:
                tx = TokenContract.functions.setReturnDetails(form.return_details.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # 有効期限変更
            if form.expirationDate.data != expirationDate:
                tx = TokenContract.functions.setExpirationDate(form.expirationDate.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # メモ欄変更
            if form.memo.data != memo:
                tx = TokenContract.functions.setMemo(form.memo.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # 譲渡制限変更
            if form.transferable.data != transferable:
                tmpVal = True
                if form.transferable.data == 'False':
                    tmpVal = False
                tx = TokenContract.functions.setTransferable(tmpVal). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # 画像変更
            if form.image_1.data != image_1:
                tx = TokenContract.functions.setImageURL(0, form.image_1.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            if form.image_2.data != image_2:
                tx = TokenContract.functions.setImageURL(1, form.image_2.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            if form.image_3.data != image_3:
                tx = TokenContract.functions.setImageURL(2, form.image_3.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # DEXアドレス変更
            if form.tradableExchange.data != tradableExchange:
                tx = TokenContract.functions.setTradableExchange(to_checksum_address(form.tradableExchange.data)). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # 問い合わせ先変更
            if form.contact_information.data != contact_information:
                tx = TokenContract.functions.setContactInformation(form.contact_information.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # プライバシーポリシー変更
            if form.privacy_policy.data != privacy_policy:
                tx = TokenContract.functions.setPrivacyPolicy(form.privacy_policy.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            flash('変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
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
                'membership/setting.html',
                form=form, token_address=token_address,
                isRelease=isRelease, status=status, token_name=name
            )
    else:  # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.details.data = details
        form.return_details.data = return_details
        form.expirationDate.data = expirationDate
        form.memo.data = memo
        form.transferable.data = transferable
        form.image_1.data = image_1
        form.image_2.data = image_2
        form.image_3.data = image_3
        form.tradableExchange.data = tradableExchange
        form.contact_information.data = contact_information
        form.privacy_policy.data = privacy_policy
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'membership/setting.html',
            form=form,
            token_address=token_address,
            token_name=name,
            isRelease=isRelease,
            status=status,
            initial_offering_status=initial_offering_status
        )


####################################################
# 公開
####################################################
@membership.route('/release', methods=['POST'])
@login_required
def release():
    logger.info(f'[{current_user.login_id}] membership/release')
    token_address = request.form.get('token_address')

    # 発行体が管理するトークンかチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    issuer = Issuer.query.get(session['issuer_id'])
    list_contract_address = issuer.token_list_contract_address
    ListContract = ContractUtils.get_contract('TokenList', list_contract_address)
    try:
        tx = ListContract.functions.register(token_address, 'IbetMembership'). \
            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
        flash('処理を受け付けました。', 'success')
    except ValueError:
        flash('既に公開されています。', 'error')
    return redirect(url_for('.setting', token_address=token_address))


####################################################
# 新規発行
####################################################
@membership.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info(f'[{current_user.login_id}] membership.issue')
    form = IssueForm()

    if request.method == 'POST':
        if form.validate():
            # Exchangeコントラクトのアドレスフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                return render_template('membership/issue.html', form=form, form_description=form.description)

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
                form.expirationDate.data,
                form.memo.data,
                tmpVal,
                form.contact_information.data,
                form.privacy_policy.data
            ]
            _, bytecode, bytecode_runtime = ContractUtils.get_contract_info('IbetMembership')
            contract_address, abi, tx_hash = ContractUtils.deploy_contract('IbetMembership', arguments,
                                                                           session['eth_account'])

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_MEMBERSHIP
            token.tx_hash = tx_hash
            token.admin_address = session['eth_account'].lower()
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            # 商品画像URLの登録処理
            if form.image_1.data != '' or form.image_2.data != '' or form.image_3.data != '':
                if contract_address is not None:
                    TokenContract = web3.eth.contract(address=contract_address, abi=abi)
                    if form.image_1.data != '':
                        tx = TokenContract.functions.setImageURL(0, form.image_1.data). \
                            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
                    if form.image_2.data != '':
                        tx = TokenContract.functions.setImageURL(1, form.image_2.data). \
                            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
                    if form.image_3.data != '':
                        tx = TokenContract.functions.setImageURL(2, form.image_3.data). \
                            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('membership/issue.html', form=form, form_description=form.description)
    else:  # GET
        issuer = Issuer.query.get(session['issuer_id'])
        form.tradableExchange.data = issuer.ibet_membership_exchange_contract_address
        return render_template('membership/issue.html', form=form, form_description=form.description)


####################################################
# 保有一覧（売出管理画面）
####################################################
@membership.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info(f'[{current_user.login_id}] membership/positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_MEMBERSHIP,
        admin_address=session['eth_account'].lower()
    ).all()

    position_list = []
    for row in tokens:
        if row.token_address is not None:
            owner = to_checksum_address(row.admin_address)
            try:
                # Tokenコントラクトに接続
                TokenContract = web3.eth.contract(
                    address=row.token_address,
                    abi=json.loads(
                        row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                )

                # Exchange
                token_exchange_address = TokenContract.functions.tradableExchange().call()
                ExchangeContract = \
                    ContractUtils.get_contract('IbetMembershipExchange', token_exchange_address)

                # トークン名称
                name = TokenContract.functions.name().call()

                # トークン略称
                symbol = TokenContract.functions.symbol().call()

                # 総発行量
                total_supply = TokenContract.functions.totalSupply().call()

                # 残高
                balance = TokenContract.functions.balanceOf(owner).call()

                # 拘束中数量
                try:
                    commitment = ExchangeContract.functions.commitmentOf(owner, row.token_address).call()
                except Exception as e:
                    logger.warning(e)
                    commitment = 0
                    pass

                # 売出状態、注文ID、売出価格
                order = Order.query. \
                    filter(Order.token_address == row.token_address). \
                    filter(Order.exchange_address == token_exchange_address). \
                    filter(Order.account_address == owner). \
                    filter(Order.is_buy == False). \
                    filter(Order.is_cancelled == False). \
                    first()
                if order is not None:
                    on_sale = True
                    order_id = order.order_id
                    order_price = order.price
                else:  # 未発注の場合
                    on_sale = False
                    order_id = None
                    order_price = None

                # 調達額
                agreement_sum = db.session.query(func.sum(Agreement.price * Agreement.amount)). \
                    filter(Agreement.token_address == row.token_address). \
                    filter(Agreement.exchange_address == token_exchange_address). \
                    filter(Agreement.seller_address == owner). \
                    filter(Agreement.status == AgreementStatus.DONE.value). \
                    group_by(Agreement.token_address). \
                    first()
                if agreement_sum is not None:
                    fundraise = agreement_sum[0]
                else:
                    fundraise = 0

                position_list.append({
                    'token_address': row.token_address,
                    'name': name,
                    'symbol': symbol,
                    'total_supply': total_supply,
                    'balance': balance,
                    'commitment': commitment,
                    'order_price': order_price,
                    'fundraise': fundraise,
                    'on_sale': on_sale,
                    'order_id': order_id
                })
            except Exception as e:
                logger.error(e)
                continue

    return render_template('membership/positions.html', position_list=position_list)


####################################################
# 売出
####################################################
@membership.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info(f'[{current_user.login_id}] membership/sell')
    form = SellForm()

    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
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
    return_details = TokenContract.functions.returnDetails().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    memo = TokenContract.functions.memo().call()
    transferable = TokenContract.functions.transferable().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    status = TokenContract.functions.status().call()
    balance = TokenContract.functions.balanceOf(session['eth_account']).call()

    if request.method == 'POST':
        if form.validate():
            issuer = Issuer.query.get(session['issuer_id'])
            agent_address = issuer.agent_address

            # DEXに対してDeposit
            tx = TokenContract.functions.transfer(tradableExchange, balance). \
                buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 売注文実行
            ExchangeContract = ContractUtils.get_contract('IbetMembershipExchange', tradableExchange)
            tx = ExchangeContract.functions. \
                createOrder(token_address, balance, form.sellPrice.data, False, agent_address). \
                buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            time.sleep(3)  # NOTE: バックプロセスによるDB反映までにタイムラグがあるため3秒待つ
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
        form.return_details.data = return_details
        form.expirationDate.data = expirationDate
        form.memo.data = memo
        form.transferable.data = transferable
        form.status.data = status
        form.tradableExchange.data = tradableExchange
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template(
            'membership/sell.html',
            token_address=token_address,
            token_name=name,
            form=form
        )


####################################################
# 売出停止
####################################################
@membership.route('/cancel_order/<string:token_address>/<int:order_id>', methods=['GET', 'POST'])
@login_required
def cancel_order(token_address, order_id):
    logger.info(f'[{current_user.login_id}] membership/cancel_order')
    form = CancelOrderForm()

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    # Exchangeコントラクトに接続
    token_exchange_address = TokenContract.functions.tradableExchange().call()
    ExchangeContract = ContractUtils. \
        get_contract('IbetMembershipExchange', token_exchange_address)

    # 注文情報を取得する
    orderBook = ExchangeContract.functions.getOrder(order_id).call()
    token_address = orderBook[1]
    amount = orderBook[2]
    price = orderBook[3]

    # トークンの商品名、略称、総発行量を取得する
    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            tx = ExchangeContract.functions.cancelOrder(order_id). \
                buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            time.sleep(3)  # NOTE: バックプロセスによるDB反映までにタイムラグがあるため3秒待つ
            flash('売出停止処理を受け付けました。停止されるまでに数分程かかることがあります。', 'success')
            return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return redirect(url_for('.cancel_order', order_id=order_id))
    else:  # GET
        form.order_id.data = order_id
        form.token_address.data = token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.amount.data = amount
        form.price.data = price
        return render_template('membership/cancel_order.html', form=form)


####################################################
# 追加発行
####################################################
@membership.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info(f'[{current_user.login_id}] membership/add_supply')

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    form = AddSupplyForm()
    form.token_address.data = token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.totalSupply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            tx = TokenContract.functions.issue(form.addSupply.data). \
                buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template(
                'membership/add_supply.html',
                form=form,
                token_address=token_address,
                token_name=name
            )
    else:  # GET
        return render_template(
            'membership/add_supply.html',
            form=form,
            token_address=token_address,
            token_name=name
        )


####################################################
# 有効化/無効化
####################################################
@membership.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info(f'[{current_user.login_id}] membership/valid')
    token_address = request.form.get('token_address')
    _set_validity(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@membership.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info(f'[{current_user.login_id}] membership/invalid')
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
    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    try:
        tx = TokenContract.functions.setStatus(isvalid). \
            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.error(e)
        flash('更新処理でエラーが発生しました。', 'error')


####################################################
# 募集申込開始/停止
####################################################
@membership.route('/start_initial_offering', methods=['POST'])
@login_required
def start_initial_offering():
    logger.info(f'[{current_user.login_id}] membership/start_initial_offering')
    token_address = request.form.get('token_address')
    _set_offering_status(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@membership.route('/stop_initial_offering', methods=['POST'])
@login_required
def stop_initial_offering():
    logger.info(f'[{current_user.login_id}] membership/stop_initial_offering')
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
    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    try:
        tx = TokenContract.functions.setInitialOfferingStatus(status). \
            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.error(e)
        flash('更新処理でエラーが発生しました。', 'error')


#################################################
# 一括強制移転
#################################################

# 一括強制移転CSVアップロード
@membership.route('/bulk_transfer', methods=['GET', 'POST'])
@login_required
def bulk_transfer():
    form = BulkTransferUploadForm()

    #########################
    # GET：アップロード画面参照
    #########################
    if request.method == "GET":
        logger.info(f"[{current_user.login_id}] membership/bulk_transfer(GET)")
        return render_template("membership/bulk_transfer.html", form=form)

    #########################
    # POST：ファイルアップロード
    #########################
    if request.method == "POST":
        logger.info(f"[{current_user.login_id}] membership/bulk_transfer(POST)")

        # Formバリデート
        if form.validate() is False:
            flash_errors(form)
            return render_template("membership/bulk_transfer.html", form=form)

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
            return render_template("membership/bulk_transfer.html", form=form)

        # レコード存在チェック
        if record_count == 0:
            flash("レコードが0件のファイルはアップロードできません。", "error")
            return render_template("membership/bulk_transfer.html", form=form)

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
                return render_template("membership/bulk_transfer.html", form=form)

            # <CHK>アドレスフォーマットチェック（token_address）
            if not Web3.isAddress(token_address):
                flash(f"{i + 1}行目に無効なトークンアドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("membership/bulk_transfer.html", form=form)

            # <CHK>全てのトークンアドレスが同一のものであることのチェック
            if i == 0:
                token_address_0 = token_address
            if token_address_0 != token_address:
                flash(f"ファイル内に異なるトークンアドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("membership/bulk_transfer.html", form=form)

            # <CHK>発行体が管理するトークンであることをチェック
            token = Token.query. \
                filter(Token.token_address == token_address). \
                filter(Token.admin_address == session['eth_account'].lower()). \
                filter(Token.template_id == Config.TEMPLATE_ID_MEMBERSHIP). \
                first()
            if token is None:
                flash(f"ファイル内に未発行のトークンアドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("membership/bulk_transfer.html", form=form)

            # <CHK>アドレスフォーマットチェック（from_address）
            if not Web3.isAddress(from_address):
                flash(f"{i + 1}行目に無効な移転元アドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("membership/bulk_transfer.html", form=form)

            # <CHK>アドレスフォーマットチェック（to_address）
            if not Web3.isAddress(to_address):
                flash(f"{i + 1}行目に無効な移転先アドレスが含まれています。", "error")
                db.session.rollback()
                return render_template("membership/bulk_transfer.html", form=form)

            # <CHK>移転数量のフォーマットチェック
            if not transfer_amount.isdecimal():
                flash(f"{i + 1}行目に無効な移転数量が含まれています。", "error")
                db.session.rollback()
                return render_template("membership/bulk_transfer.html", form=form)

            # DB登録処理（一括強制移転）
            _bulk_transfer = BulkTransfer()
            _bulk_transfer.eth_account = session['eth_account']
            _bulk_transfer.upload_id = upload_id
            _bulk_transfer.token_address = token_address
            _bulk_transfer.template_id = Config.TEMPLATE_ID_MEMBERSHIP
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
        _bulk_transfer_upload.template_id = Config.TEMPLATE_ID_MEMBERSHIP
        _bulk_transfer_upload.approved = False
        db.session.add(_bulk_transfer_upload)

        db.session.commit()
        flash("ファイルアップロードが成功しました。", "success")
        return redirect(url_for('.bulk_transfer'))


# 一括強制移転サンプルCSVダウンロード
@membership.route('/bulk_transfer/sample', methods=['POST'])
@login_required
def bulk_transfer_sample():
    logger.info(f"[{current_user.login_id}] membership/bulk_transfer_sample")

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
@membership.route('/bulk_transfer_history', methods=['GET'])
@login_required
def bulk_transfer_history():
    logger.info(f'[{current_user.login_id}] membership/bulk_transfer_history')

    records = BulkTransferUpload.query. \
        filter(BulkTransferUpload.eth_account == session["eth_account"]). \
        filter(BulkTransferUpload.template_id == Config.TEMPLATE_ID_MEMBERSHIP). \
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
@membership.route('/bulk_transfer_approval/<string:upload_id>', methods=['GET', 'POST'])
@login_required
def bulk_transfer_approval(upload_id):

    #########################
    # GET：移転指示データ参照
    #########################
    if request.method == "GET":
        logger.info(f"[{current_user.login_id}] membership/bulk_transfer_approval(GET)")

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
            "membership/bulk_transfer_approval.html",
            upload_id=upload_id,
            approved=approved,
            transfer_list=transfer_list
        )

    #########################
    # POST：移転指示データ承認
    #########################
    if request.method == "POST":
        logger.info(f'[{current_user.login_id}] membership/bulk_transfer_approval(POST)')

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
@membership.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')
