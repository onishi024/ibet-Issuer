# -*- coding:utf-8 -*-
import json
import base64
import io
import re
import time
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=+9), 'JST')

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from flask import request, redirect, url_for, flash, make_response, render_template, abort, jsonify
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.util import eth_unlock_account, get_holder
from app.models import Token, Order, Agreement, AgreementStatus, AddressType, ApplyFor, Transfer
from app.contracts import Contract
from config import Config
from . import membership
from .forms import TransferForm, TransferOwnershipForm, SettingForm, SellForm, IssueForm, CancelOrderForm, AddSupplyForm

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


# 共通処理：トークン移転（強制移転）
def transfer_token(token_contract, from_address, to_address, amount):
    eth_unlock_account()
    gas = token_contract.estimateGas().transferFrom(from_address, to_address, amount)
    tx_hash = token_contract.functions.transferFrom(from_address, to_address, amount). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
    return tx_hash


####################################################
# [会員権]発行済一覧
####################################################
@membership.route('/list', methods=['GET'])
@login_required
def list():
    logger.info('membership.list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()

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
                # utc→jst の変換
                created = datetime.fromtimestamp(row.created.timestamp(), JST)

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
# [会員権]募集申込一覧
####################################################
# 申込一覧画面
@membership.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info('membership/applications')
    return render_template(
        'membership/applications.html',
        token_address=token_address,
    )


# 申込者リストCSVダウンロード
@membership.route('/applications_csv_download', methods=['POST'])
@login_required
def applications_csv_download():
    logger.info('membership/applications_csv_download')

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

    now = datetime.fromtimestamp(datetime.utcnow().timestamp(), JST)
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
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except Exception as e:
        logger.error(e)

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

    # 申込（ApplyFor）イベントを検索
    apply_for_events = ApplyFor.query. \
        distinct(ApplyFor.account_address). \
        filter(ApplyFor.token_address == token_address).all()

    # 募集申込の履歴が存在するアカウントアドレスのリストを作成
    account_list = []
    for event in apply_for_events:
        account_list.append(event.account_address)

    token_owner = TokenContract.functions.owner().call()
    applications = []
    for account_address in account_list:
        encrypted_info = PersonalInfoContract.functions. \
            personal_info(account_address, token_owner).call()[2]

        account_name = ''
        account_email_address = ''
        if encrypted_info == '' or cipher is None:
            pass
        else:
            try:
                ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                message = cipher.decrypt(ciphertext)
                personal_info_json = json.loads(message)
                if 'name' in personal_info_json:
                    account_name = personal_info_json['name']
                if 'email' in personal_info_json:
                    account_email_address = personal_info_json['email']
            except Exception as e:
                logger.warning(e)
                pass

        data = TokenContract.functions.applications(account_address).call()

        application = {
            'account_address': account_address,
            'account_name': account_name,
            'account_email_address': account_email_address,
            'data': data
        }
        applications.append(application)

    return jsonify(applications)


####################################################
# [会員権]割当（募集申込）
####################################################
@membership.route('/allocate/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def allocate(token_address, account_address):
    logger.info('membership/allocate')

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
                    'membership/allocate.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            # 割当処理（発行体アドレス→指定アドレス）
            from_address = Config.ETH_ACCOUNT
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
# [会員権]保有者一覧
####################################################
@membership.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('membership/holders')
    return render_template(
        'membership/holders.html',
        token_address=token_address
    )


# 保有者リストCSVダウンロード
@membership.route('/holders_csv_download', methods=['POST'])
@login_required
def holders_csv_download():
    logger.info('membership/holders_csv_download')

    token_address = request.form.get('token_address')
    holders = json.loads(get_holders(token_address).data)
    token_name = json.loads(get_token_name(token_address).data)

    f = io.StringIO()

    # ヘッダー行
    data_header = \
        'token_name,' + \
        'token_address,' + \
        'account_address,' + \
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
            token_name + ',' + token_address + ',' + holder["account_address"] + ',' + \
            str(holder["balance"]) + ',' + str(holder["commitment"]) + ',' + \
            holder["name"] + ',' + holder["birth_date"] + ',' + \
            holder["postal_code"] + ',' + holder_address + ',' + \
            holder["email"] + '\n'
        f.write(data_row)

    now = datetime.fromtimestamp(datetime.utcnow().timestamp(), JST)
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
    logger.info('membership/get_holders')

    # RSA秘密鍵の取得
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except Exception as e:
        logger.error(e)

    # Token情報取得
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # Tokenコントラクト接続
    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    # 取引コントラクトの情報取得
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as e:
        logger.error(e)
        tradable_exchange = '0x0000000000000000000000000000000000000000'
        pass

    # 取引コントラクト接続
    ExchangeContract = Contract.get_contract('IbetMembershipExchange', tradable_exchange)

    # 個人情報コントラクト接続
    personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
    PersonalInfoContract = Contract.get_contract('PersonalInfo', personalinfo_address)

    # Transferイベントを検索
    transfer_events = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address).all()

    # 残高を保有している可能性のあるアドレスを抽出する
    token_owner = TokenContract.functions.owner().call()  # トークン発行体アドレスを取得
    holders_temp = [token_owner]  # 発行体アドレスをリストに追加
    for event in transfer_events:
        holders_temp.append(event.account_address_to)

    # 口座リストをユニークにする
    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    # 保有者情報抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        try:
            commitment = ExchangeContract.functions.commitmentOf(account_address, token_address).call()
        except Exception as e:
            logger.warning(e)
            commitment = 0
            pass
        if balance > 0 or commitment > 0:  # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
            # アドレス種別判定
            if account_address == token_owner:
                address_type = AddressType.ISSUER.value
            elif account_address == tradable_exchange:
                address_type = AddressType.EXCHANGE.value
            else:
                address_type = AddressType.OTHERS.value

            # 保有者情報：初期値（個人情報なし）
            holder = {
                'account_address': account_address,
                'name': '--',
                'postal_code': '--',
                'email': '--',
                'address': '--',
                'birth_date': '--',
                'balance': balance,
                'commitment': commitment,
                'address_type': address_type
            }

            # 暗号化個人情報取得
            try:
                encrypted_info = PersonalInfoContract.functions.personal_info(account_address, token_owner).call()[2]
            except Exception as e:
                logger.warning(e)
                encrypted_info = ''
                pass

            if encrypted_info == '' or cipher is None:  # 情報が空の場合、デフォルト値の設定
                pass
            else:
                try:
                    # 個人情報復号化
                    ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                    message = cipher.decrypt(ciphertext)
                    personal_info_json = json.loads(message)
                    name = personal_info_json['name'] if personal_info_json['name'] else "--"
                    if personal_info_json['address']['prefecture'] and personal_info_json['address']['city'] and \
                            personal_info_json['address']['address1']:
                        address = personal_info_json['address']['prefecture'] + personal_info_json['address']['city']
                        if personal_info_json['address']['address1'] != "":
                            address = address + "　" + personal_info_json['address']['address1']
                        if personal_info_json['address']['address2'] != "":
                            address = address + "　" + personal_info_json['address']['address2']
                    else:
                        address = "--"
                    postal_code = personal_info_json['address']['postal_code'] if personal_info_json['address'][
                        'postal_code'] else "--"
                    email = personal_info_json['email'] if personal_info_json['email'] else "--"
                    birth_date = personal_info_json['birth'] if personal_info_json['birth'] else "--"
                    # 保有者情報（個人情報あり）
                    holder = {
                        'account_address': account_address,
                        'name': name,
                        'postal_code': postal_code,
                        'email': email,
                        'address': address,
                        'birth_date': birth_date,
                        'balance': balance,
                        'commitment': commitment,
                        'address_type': address_type
                    }
                except Exception as e:
                    logger.warning(e)
                    pass

            holders.append(holder)

    return jsonify(holders)


@membership.route('/get_token_name/<string:token_address>', methods=['GET'])
@login_required
def get_token_name(token_address):
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    token_name = TokenContract.functions.name().call()

    return jsonify(token_name)


####################################################
# [会員権]保有者移転
####################################################
@membership.route('/transfer_ownership/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info('membership/transfer_ownership')

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
# [会員権]保有者詳細
####################################################
@membership.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('membership/holder')
    personal_info = get_holder(token_address, account_address)
    return render_template(
        'membership/holder.html',
        personal_info=personal_info,
        token_address=token_address
    )


####################################################
# [会員権]設定内容修正
####################################################
@membership.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('membership.setting')

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
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract('TokenList', list_contract_address)
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

            # アカウントアンロック
            eth_unlock_account()

            # トークン詳細変更
            if form.details.data != details:
                gas = TokenContract.estimateGas().setDetails(form.details.data)
                TokenContract.functions.setDetails(form.details.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # 特典詳細変更
            if form.return_details.data != return_details:
                gas = TokenContract.estimateGas().setReturnDetails(form.return_details.data)
                TokenContract.functions.setReturnDetails(form.return_details.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # 有効期限変更
            if form.expirationDate.data != expirationDate:
                gas = TokenContract.estimateGas().setExpirationDate(form.expirationDate.data)
                TokenContract.functions.setExpirationDate(form.expirationDate.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # メモ欄変更
            if form.memo.data != memo:
                gas = TokenContract.estimateGas().setMemo(form.memo.data)
                TokenContract.functions.setMemo(form.memo.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # 譲渡制限変更
            if form.transferable.data != transferable:
                tmpVal = True
                if form.transferable.data == 'False':
                    tmpVal = False
                gas = TokenContract.estimateGas().setTransferable(tmpVal)
                TokenContract.functions.setTransferable(tmpVal).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # 画像変更
            if form.image_1.data != image_1:
                gas = TokenContract.estimateGas().setImageURL(0, form.image_1.data)
                TokenContract.functions.setImageURL(0, form.image_1.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
            if form.image_2.data != image_2:
                gas = TokenContract.estimateGas().setImageURL(1, form.image_2.data)
                TokenContract.functions.setImageURL(1, form.image_2.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
            if form.image_3.data != image_3:
                gas = TokenContract.estimateGas().setImageURL(2, form.image_3.data)
                TokenContract.functions.setImageURL(2, form.image_3.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # DEXアドレス変更
            if form.tradableExchange.data != tradableExchange:
                gas = TokenContract.estimateGas().setTradableExchange(to_checksum_address(form.tradableExchange.data))
                TokenContract.functions.setTradableExchange(
                    to_checksum_address(form.tradableExchange.data)).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

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
# [会員権]公開
####################################################
@membership.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('membership/release')
    eth_unlock_account()

    token_address = request.form.get('token_address')
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract(
        'TokenList', list_contract_address)

    try:
        gas = ListContract.estimateGas(). \
            register(token_address, 'IbetMembership')
        tx = ListContract.functions. \
            register(token_address, 'IbetMembership'). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except ValueError:
        flash('既に公開されています。', 'error')

    return redirect(url_for('.setting', token_address=token_address))


####################################################
# [会員権]新規発行
####################################################
@membership.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('membership.issue')
    form = IssueForm()

    if request.method == 'POST':
        if form.validate():
            # Exchangeコントラクトのアドレスフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                return render_template('membership/issue.html', form=form, form_description=form.description)

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
                form.expirationDate.data,
                form.memo.data,
                tmpVal,
                form.contact_information.data,
                form.privacy_policy.data
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetMembership')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract('IbetMembership', arguments, Config.ETH_ACCOUNT)

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_MEMBERSHIP
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            # 商品画像URLの登録処理
            if form.image_1.data != '' or form.image_2.data != '' or form.image_3.data != '':
                tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
                if tx_receipt is not None:
                    TokenContract = web3.eth.contract(
                        address=tx_receipt['contractAddress'],
                        abi=abi
                    )
                    if form.image_1.data != '':
                        gas = TokenContract.estimateGas().setImageURL(0, form.image_1.data)
                        TokenContract.functions.setImageURL(0, form.image_1.data).transact(
                            {'from': Config.ETH_ACCOUNT, 'gas': gas}
                        )
                    if form.image_2.data != '':
                        gas = TokenContract.estimateGas().setImageURL(1, form.image_2.data)
                        TokenContract.functions.setImageURL(1, form.image_2.data).transact(
                            {'from': Config.ETH_ACCOUNT, 'gas': gas}
                        )
                    if form.image_3.data != '':
                        gas = TokenContract.estimateGas().setImageURL(2, form.image_3.data)
                        TokenContract.functions.setImageURL(2, form.image_3.data).transact(
                            {'from': Config.ETH_ACCOUNT, 'gas': gas}
                        )

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('membership/issue.html', form=form, form_description=form.description)
    else:  # GET
        form.tradableExchange.data = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
        return render_template('membership/issue.html', form=form, form_description=form.description)


####################################################
# [会員権]保有一覧（売出管理画面）
####################################################
@membership.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('membership/positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()

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
                    Contract.get_contract('IbetMembershipExchange', token_exchange_address)

                # トークン名称
                name = TokenContract.functions.name().call()

                # トークン略称
                symbol = TokenContract.functions.symbol().call()

                # 総発行量
                total_supply = TokenContract.functions.totalSupply().call()

                # 残高
                balance = TokenContract.functions.balanceOf(owner).call()

                # utc→jst の変換
                created = datetime.fromtimestamp(row.created.timestamp(), JST)

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
                if order is not None and order.amount != 0:
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
                    'created': created,
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
# [会員権]売出
####################################################
@membership.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('membership/sell')
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
    return_details = TokenContract.functions.returnDetails().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    memo = TokenContract.functions.memo().call()
    transferable = TokenContract.functions.transferable().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    status = TokenContract.functions.status().call()
    balance = TokenContract.functions.balanceOf(Config.ETH_ACCOUNT).call()

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()

            token_exchange_address = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
            agent_address = Config.AGENT_ADDRESS

            deposit_gas = TokenContract.estimateGas(). \
                transfer(token_exchange_address, balance)
            TokenContract.functions. \
                transfer(token_exchange_address, balance). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})

            ExchangeContract = Contract.get_contract(
                'IbetMembershipExchange', token_exchange_address)
            sell_gas = ExchangeContract.estimateGas(). \
                createOrder(token_address, balance, form.sellPrice.data, False, agent_address)
            txid = ExchangeContract.functions. \
                createOrder(token_address, balance, form.sellPrice.data, False, agent_address). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': sell_gas})
            web3.eth.waitForTransactionReceipt(txid)
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
# [会員権]売出停止
####################################################
@membership.route('/cancel_order/<string:token_address>/<int:order_id>', methods=['GET', 'POST'])
@login_required
def cancel_order(token_address, order_id):
    logger.info('membership/cancel_order')
    form = CancelOrderForm()

    # トークンのABIを取得する
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract. \
        get_contract('IbetMembershipExchange', token_exchange_address)

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

    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            gas = ExchangeContract.estimateGas().cancelOrder(order_id)
            txid = ExchangeContract.functions.cancelOrder(order_id). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            web3.eth.waitForTransactionReceipt(txid)
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
# [会員権]追加発行
####################################################
@membership.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info('membership/add_supply')

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
            eth_unlock_account()
            gas = TokenContract.estimateGas().issue(form.addSupply.data)
            TokenContract.functions.issue(form.addSupply.data).transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
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
# [会員権]有効化/無効化
####################################################
@membership.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info('membership/valid')
    token_address = request.form.get('token_address')
    membership_valid(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@membership.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info('membership/invalid')
    token_address = request.form.get('token_address')
    membership_valid(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def membership_valid(token_address, isvalid):
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
        logger.error(e)
        flash('更新処理でエラーが発生しました。', 'error')


####################################################
# [会員権]募集申込開始/停止
####################################################
@membership.route('/start_initial_offering', methods=['POST'])
@login_required
def start_initial_offering():
    logger.info('membership/start_initial_offering')
    token_address = request.form.get('token_address')
    set_initial_offering_status(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@membership.route('/stop_initial_offering', methods=['POST'])
@login_required
def stop_initial_offering():
    logger.info('membership/stop_initial_offering')
    token_address = request.form.get('token_address')
    set_initial_offering_status(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def set_initial_offering_status(token_address, status):
    eth_unlock_account()
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

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


####################################################
# [会員権]権限エラー
####################################################
@membership.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')
