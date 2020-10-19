# -*- coding:utf-8 -*-
import base64
import io
import json
import re
from datetime import datetime, timezone, timedelta
import time
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from flask_wtf import FlaskForm as Form
from flask import request, redirect, url_for, flash, make_response, \
    render_template, abort, jsonify, session
from flask_login import login_required

from sqlalchemy import func, desc
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

from app import db
from app.exceptions import EthRuntimeError
from app.models import Token, Certification, Order, Agreement, AgreementStatus, \
    Transfer, AddressType, ApplyFor, Issuer, HolderList, LedgerAdministrator, BondLedger
from app.utils import ContractUtils, TokenUtils
from config import Config

from . import bond
from .forms import TransferOwnershipForm, SettingForm, RequestSignatureForm, \
    IssueForm, SellTokenForm, CancelOrderForm, TransferForm, \
    AllotForm, AddSupplyForm, LedgerAdministratorForm

from logging import getLogger

logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
JST = timezone(timedelta(hours=+9), 'JST')


####################################################
# 共通処理
####################################################
def flash_errors(form: Form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


def default_interest_payment_date():
    """
    利払日オブジェクトのデフォルト値
    """
    return {
        f'interestPaymentDate{index}': '' for index in range(1, 13)
    }


def map_interest_payment_date(form, interestPaymentDate):
    """
    利払日オブジェクトのFormへのマッピング
    :param form: Form
    :param interestPaymentDate: 利払日（JSONオブジェクト）
    :return: なし
    """
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


####################################################
# [債券]トークン名取得
####################################################
@bond.route('/get_token_name/<string:token_address>', methods=['GET'])
@login_required
def get_token_name(token_address):
    logger.info('bond/get_token_name')

    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])
    token_name = TokenContract.functions.name().call()

    return jsonify(token_name)


####################################################
# [債券]新規発行
####################################################

@bond.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('bond/issue')
    form = IssueForm()

    if request.method == 'POST':
        if form.validate():
            # 年利：小数点有効桁数チェック
            if not form.check_decimal_places(4, form.interestRate):
                flash('年利は小数点4桁以下で入力してください。', 'error')
                return render_template('bond/issue.html', form=form, form_description=form.description)

            # Exchangeコントラクトのアドレスフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                return render_template('bond/issue.html', form=form, form_description=form.description)

            # PersonalInfoコントラクトのアドレスフォーマットチェック
            if not Web3.isAddress(form.personalInfoAddress.data):
                flash('個人情報コントラクトは有効なアドレスではありません。', 'error')
                return render_template('bond/issue.html', form=form, form_description=form.description)

            # トークン発行（トークンコントラクトのデプロイ）
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

            # 任意設定項目のデフォルト値変換（償還金額）
            if form.redemptionValue.data is None:
                redemption_value = 0
            else:
                redemption_value = form.redemptionValue.data

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                form.faceValue.data,
                form.redemptionDate.data,
                redemption_value,
                form.returnDate.data,
                form.returnDetails.data,
                form.purpose.data,
            ]
            _, bytecode, bytecode_runtime = ContractUtils.get_contract_info('IbetStraightBond')
            contract_address, abi, tx_hash = \
                ContractUtils.deploy_contract('IbetStraightBond', arguments, session['eth_account'])

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_SB
            token.tx_hash = tx_hash
            token.admin_address = session['eth_account'].lower()
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            if contract_address is not None:
                TokenContract = web3.eth.contract(address=contract_address, abi=abi)

                # 年利の登録処理
                interestRate = int(form.interestRate.data * 10000)
                if interestRate != 0:
                    tx = TokenContract.functions.setInterestRate(interestRate). \
                        buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 利払日の登録処理
                tx = TokenContract.functions.setInterestPaymentDate(interestPaymentDate_string). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # メモの登録処理
                if form.memo.data:
                    tx = TokenContract.functions.setMemo(form.memo.data). \
                        buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 商品画像URLの登録処理
                if form.image_1.data != '' or form.image_2.data != '' or form.image_3.data != '':
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

                # 譲渡可否設定の登録処理
                # NOTE:デフォルト設定は譲渡可能（True）なので、譲渡不可（False）の場合にのみ、更新処理を行う
                if form.transferable.data == "False":
                    tx = TokenContract.functions.setTransferable(False). \
                        buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 問い合わせ先の登録処理
                if form.contact_information.data:
                    tx = TokenContract.functions.setContactInformation(form.contact_information.data). \
                        buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # プライバシーポリシーの登録処理
                if form.privacy_policy.data:
                    tx = TokenContract.functions.setPrivacyPolicy(form.privacy_policy.data). \
                        buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                    ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 個人情報コントラクトの登録処理
                personal_info_address = form.personalInfoAddress.data
                tx = TokenContract.functions.setPersonalInfoAddress(personal_info_address). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # DEXアドレスの登録処理
                tradable_exchange = to_checksum_address(form.tradableExchange.data)
                tx = TokenContract.functions.setTradableExchange(tradable_exchange). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('bond/issue.html', form=form, form_description=form.description)
    else:  # GET
        issuer = Issuer.query.get(session['issuer_id'])
        form.tradableExchange.data = issuer.ibet_sb_exchange_contract_address
        form.personalInfoAddress.data = issuer.personal_info_contract_address
        return render_template('bond/issue.html', form=form, form_description=form.description)


####################################################
# [債券]発行済一覧
####################################################
@bond.route('/list', methods=['GET'])
@login_required
def list():
    logger.info('bond/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_SB,
        admin_address=session['eth_account'].lower()
    ).all()

    token_list = []
    for row in tokens:
        try:
            is_redeemed = False

            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address is None:
                name = '--'
                symbol = '--'
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
                is_redeemed = TokenContract.functions.isRedeemed().call()

            # 作成日時（JST）
            created = datetime.fromtimestamp(row.created.timestamp(), JST).strftime("%Y/%m/%d %H:%M:%S %z")

            token_list.append({
                'name': name,
                'symbol': symbol,
                'created': created,
                'tx_hash': row.tx_hash,
                'token_address': row.token_address,
                'is_redeemed': is_redeemed
            })
        except Exception as e:
            logger.error(e)
            pass

    return render_template('bond/list.html', tokens=token_list)


####################################################
# [債券]保有者一覧
####################################################
@bond.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('bond/holders')
    return render_template('bond/holders.html', token_address=token_address)


# 保有者リストCSVダウンロード
@bond.route('/holders_csv_download', methods=['POST'])
@login_required
def holders_csv_download():
    logger.info('bond/holders_csv_download')

    token_address = request.form.get('token_address')
    holders = json.loads(get_holders(token_address).data)
    token_name = json.loads(get_token_name(token_address).data)

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])
    try:
        face_value = TokenContract.functions.faceValue().call()
    except Exception as e:
        logger.error(e)
        face_value = 0
        pass

    f = io.StringIO()

    # ヘッダー行
    data_header = \
        'token_name,' + \
        'token_address,' + \
        'account_address,' + \
        'balance,' + \
        'commitment,' + \
        'total_balance,' + \
        'total_holdings,' + \
        'name,' + \
        'birth_date,' + \
        'postal_code,' + \
        'address,' + \
        'email\n'
    f.write(data_header)

    for holder in holders:
        # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
        holder_address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', holder["address"])
        # 保有数量合計
        total_balance = holder["balance"] + holder["commitment"]
        # 保有金額合計
        total_holdings = total_balance * face_value
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + holder["account_address"] + ',' + \
            str(holder["balance"]) + ',' + str(holder["commitment"]) + ',' + \
            str(total_balance) + ',' + str(total_holdings) + ',' + \
            holder["name"] + ',' + holder["birth_date"] + ',' + \
            holder["postal_code"] + ',' + holder_address + ',' + \
            holder["email"] + '\n'
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") \
                                         + 'bond_holders_list.csv'
    return res


# 保有者リスト取得
@bond.route('/get_holders/<string:token_address>', methods=['GET'])
@login_required
def get_holders(token_address):
    """
    保有者一覧取得
    :param token_address: トークンアドレス
    :return: トークンの保有者一覧
    """
    logger.info('bond/get_holders')

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    # RSA秘密鍵の取得
    issuer = Issuer.query.get(session['issuer_id'])
    cipher = None
    try:
        key = RSA.importKey(issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except Exception as err:
        logger.error(f"Cannot open the private key: {err}")

    # 取引コントラクト、個人情報コントラクトの情報取得
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
        personal_info_address = TokenContract.functions.personalInfoAddress().call()
    except Exception as err:
        logger.error(f"Failed to get token attributes: {err}")
        tradable_exchange = '0x0000000000000000000000000000000000000000'
        personal_info_address = '0x0000000000000000000000000000000000000000'

    # 債券取引コントラクト接続
    ExchangeContract = ContractUtils.get_contract('IbetStraightBondExchange', tradable_exchange)

    # 個人情報コントラクト接続
    PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', personal_info_address)

    # Transferイベントを検索
    transfer_events = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address).all()

    # 残高を保有している可能性のあるアドレスを抽出する
    token_owner = session['eth_account']
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

            if address_type == AddressType.ISSUER.value:
                issuer_info = Issuer.query.filter(Issuer.eth_account == account_address).first()

                if issuer_info is not None:
                    # 保有者情報（発行体）
                    holder = {
                        'account_address': account_address,
                        'name': issuer_info.issuer_name or '--',
                        'postal_code': '--',
                        'email': '--',
                        'address': '--',
                        'birth_date': '--',
                        'balance': balance,
                        'commitment': commitment,
                        'address_type': address_type
                    }
            else:
                # 暗号化個人情報取得
                try:
                    encrypted_info = PersonalInfoContract.functions. \
                        personal_info(account_address, token_owner).call()[2]
                except Exception as err:
                    logger.warning(f"Failed to get personal information: {err}")
                    encrypted_info = ''

                if encrypted_info == '' or cipher is None:  # 情報が空の場合、デフォルト値を設定
                    pass
                else:
                    try:
                        # 個人情報復号化
                        ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                        # NOTE:
                        # JavaScriptでRSA暗号化する際に、先頭が0x00の場合は00を削った状態でデータが連携される。
                        # そのままdecryptすると、ValueError（Ciphertext with incorrect length）になるため、
                        # 先頭に再度00を加えて、decryptを行う。
                        if len(ciphertext) == 1279:
                            hex_fixed = "00" + ciphertext.hex()
                            ciphertext = base64.b16decode(hex_fixed.upper())
                        message = cipher.decrypt(ciphertext)
                        personal_info_json = json.loads(message)

                        # 氏名
                        name = personal_info_json['name'] \
                            if personal_info_json['name'] else "--"

                        # 住所
                        if personal_info_json['address']['prefecture'] \
                                and personal_info_json['address']['city'] \
                                and personal_info_json['address']['address1']:
                            address = personal_info_json['address']['prefecture'] \
                                      + personal_info_json['address']['city']
                            if personal_info_json['address']['address1'] != "":
                                address = address + "　" + personal_info_json['address']['address1']
                            if personal_info_json['address']['address2'] != "":
                                address = address + "　" + personal_info_json['address']['address2']
                        else:
                            address = "--"

                        # 郵便番号
                        postal_code = personal_info_json['address']['postal_code'] \
                            if personal_info_json['address']['postal_code'] else "--"

                        # Eメールアドレス
                        email = personal_info_json['email'] if personal_info_json['email'] else "--"

                        # 生年月日
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
                    except Exception as err:  # 復号化処理でエラーが発生した場合、デフォルト値を設定
                        logger.error(f"Failed to decrypt: {err}")

            holders.append(holder)

    return jsonify(holders)


####################################################
# [債券]保有者リスト履歴
####################################################
@bond.route('/holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def holders_csv_history(token_address):
    logger.info('bond/holders_csv_history')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address):
        abort(404)

    return render_template(
        'bond/holders_csv_history.html',
        token_address=token_address
    )


# 保有者リスト履歴（API）
@bond.route('/get_holders_csv_history/<string:token_address>', methods=['GET'])
@login_required
def get_holders_csv_history(token_address):
    logger.info('bond/get_holders_csv_history')

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
        file_name = created_jst.strftime("%Y%m%d%H%M%S") + 'bond_holders_list.csv'
        history.append({
            'id': row.id,
            'token_address': row.token_address,
            'created': created_formatted,
            'file_name': file_name
        })

    return jsonify(history)


# 保有者リストCSVダウンロード
@bond.route('/holders_csv_history_download', methods=['POST'])
@login_required
def holders_csv_history_download():
    logger.info('bond/holders_csv_history_download')

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
                                         + 'bond_holders_list.csv'
    return res


####################################################
# [債券]保有者移転
####################################################
@bond.route('/transfer_ownership/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info('bond/transfer_ownership')

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
                    'bond/transfer_ownership.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )
            tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            # NOTE: 保有者一覧が非同期で更新されるため、5秒待つ
            time.sleep(5)
            return redirect(url_for('.holders', token_address=token_address))
        else:
            flash_errors(form)
            form.from_address.data = account_address
            return render_template(
                'bond/transfer_ownership.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        form.from_address.data = account_address
        form.to_address.data = ''
        form.amount.data = balance
        return render_template(
            'bond/transfer_ownership.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


####################################################
# [債券]保有者詳細
####################################################
@bond.route('/holder/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def holder(token_address, account_address):
    # アドレスフォーマットのチェック
    if not Web3.isAddress(token_address) or not Web3.isAddress(account_address):
        abort(404)
    token_address = to_checksum_address(token_address)
    account_address = to_checksum_address(account_address)

    # トークンで指定した個人情報コントラクトのアドレスを取得
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=session['eth_account'],
        template_id=Config.TEMPLATE_ID_SB
    )
    try:
        personal_info_address = TokenContract.functions.personalInfoAddress().call()
    except Exception as err:
        logger.exception(f"{err}")
        personal_info_address = Config.ZERO_ADDRESS

    #########################
    # GET：参照
    #########################
    if request.method == "GET":
        logger.info('bond/holder(GET)')
        personal_info = TokenUtils.get_holder(
            account_address=account_address,
            issuer_address=session['eth_account'],
            custom_personal_info_address=personal_info_address
        )
        return render_template(
            'bond/holder.html',
            personal_info=personal_info,
            token_address=token_address,
            account_address=account_address
        )

    #########################
    # POST：個人情報更新
    #########################
    if request.method == "POST":
        if request.form.get('_method') == 'DELETE':  # 個人情報初期化
            logger.info('bond/holder(DELETE)')
            try:
                TokenUtils.modify_personal_info(
                    account_address=account_address,
                    issuer_address=session['eth_account'],
                    data={},
                    custom_personal_info_address=personal_info_address
                )
                flash('個人情報の初期化に成功しました。', 'success')
            except EthRuntimeError:
                flash('個人情報の初期化に失敗しました。', 'error')

            personal_info = TokenUtils.get_holder(
                account_address=account_address,
                issuer_address=session['eth_account'],
                custom_personal_info_address=personal_info_address
            )
            return render_template(
                'bond/holder.html',
                personal_info=personal_info,
                token_address=token_address,
                account_address=account_address
            )


####################################################
# [債券]設定内容修正
####################################################
@bond.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('bond/setting')

    # 指定したトークンが存在しない場合、エラーを返す
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
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
    faceValue = TokenContract.functions.faceValue().call()
    interestRate_int = TokenContract.functions.interestRate().call()
    interestRate = interestRate_int * 0.0001
    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = json.loads(
        interestPaymentDate_string.replace("'", '"').replace('True', 'true').replace('False', 'false')) \
        if interestPaymentDate_string else default_interest_payment_date()
    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionValue = TokenContract.functions.redemptionValue().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnDetails = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()
    memo = TokenContract.functions.memo().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    image_1 = TokenContract.functions.getImageURL(0).call()
    image_2 = TokenContract.functions.getImageURL(1).call()
    image_3 = TokenContract.functions.getImageURL(2).call()
    contact_information = TokenContract.functions.contactInformation().call()
    privacy_policy = TokenContract.functions.privacyPolicy().call()
    transferable = str(TokenContract.functions.transferable().call())
    personalInfoAddress = TokenContract.functions.personalInfoAddress().call()
    initial_offering_status = TokenContract.functions.initialOfferingStatus().call()
    is_redeemed = TokenContract.functions.isRedeemed().call()

    # TokenList登録状態取得
    issuer = Issuer.query.get(session['issuer_id'])
    list_contract_address = issuer.token_list_contract_address
    ListContract = ContractUtils.get_contract('TokenList', list_contract_address)
    token_struct = ListContract.functions.getTokenByAddress(token_address).call()
    is_released = False
    if token_struct[0] == token_address:
        is_released = True

    form = SettingForm()
    if request.method == 'POST':
        if form.validate():  # Validationチェック
            # 年利変更
            formInterestRate = int(form.interestRate.data * 10000)
            if formInterestRate != interestRate_int:
                tx = TokenContract.functions.setInterestRate(formInterestRate). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 利払い日変更
            newInterestPaymentDate = {
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
            isInterestPaymentDateChanged = False
            for date in newInterestPaymentDate.keys():
                if interestPaymentDate.get(date, '') != newInterestPaymentDate[date]:
                    isInterestPaymentDateChanged = True
                    break
            if isInterestPaymentDateChanged:
                newInterestPaymentDate_string = json.dumps(newInterestPaymentDate)
                tx = TokenContract.functions.setInterestPaymentDate(newInterestPaymentDate_string). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # メモ欄変更
            if form.memo.data != memo:
                tx = TokenContract.functions.setMemo(form.memo.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # 譲渡制限変更
            if form.transferable.data != transferable:
                transferable_bool = True
                if form.transferable.data == 'False':
                    transferable_bool = False
                tx = TokenContract.functions.setTransferable(transferable_bool). \
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
                tx = TokenContract.functions. \
                    setTradableExchange(to_checksum_address(form.tradableExchange.data)). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

            # PersonalInfoコントラクトアドレス変更
            if form.personalInfoAddress.data != personalInfoAddress:
                tx = TokenContract.functions. \
                    setPersonalInfoAddress(to_checksum_address(form.personalInfoAddress.data)). \
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

            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            form.token_address.data = token.token_address
            form.name.data = name
            form.symbol.data = symbol
            form.totalSupply.data = totalSupply
            form.faceValue.data = faceValue
            form.redemptionDate.data = redemptionDate
            form.redemptionValue.data = redemptionValue
            form.returnDate.data = returnDate
            form.returnDetails.data = returnDetails
            form.purpose.data = purpose
            form.abi.data = token.abi
            form.bytecode.data = token.bytecode
            return render_template(
                'bond/setting.html',
                form=form, token_address=token_address,
                token_name=name, is_released=is_released, is_redeemed=is_redeemed,
                initial_offering_status=initial_offering_status
            )
    else:  # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        map_interest_payment_date(form, interestPaymentDate)
        form.redemptionDate.data = redemptionDate
        form.redemptionValue.data = redemptionValue
        form.returnDate.data = returnDate
        form.returnDetails.data = returnDetails
        form.purpose.data = purpose
        form.memo.data = memo
        form.transferable.data = transferable
        form.image_1.data = image_1
        form.image_2.data = image_2
        form.image_3.data = image_3
        form.tradableExchange.data = tradableExchange
        form.personalInfoAddress.data = personalInfoAddress
        form.contact_information.data = contact_information
        form.privacy_policy.data = privacy_policy
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'bond/setting.html',
            form=form,
            token_address=token_address,
            token_name=name,
            is_released=is_released,
            initial_offering_status=initial_offering_status,
            is_redeemed=is_redeemed
        )


####################################################
# [債券]第三者認定申請
####################################################
@bond.route('/request_signature/<string:token_address>', methods=['GET', 'POST'])
@login_required
def request_signature(token_address):
    logger.info('bond/request_signature')

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    form = RequestSignatureForm()
    if request.method == 'POST':
        if form.validate():

            # 指定した認定者のアドレスが有効なアドレスであるかどうかをチェックする
            if not Web3.isAddress(form.signer.data):
                flash('有効なアドレスではありません。', 'error')
                return render_template('bond/request_signature.html', form=form)

            signer_address = to_checksum_address(form.signer.data)

            # DBに既に情報が登録されている場合はエラーを返す
            if Certification.query.filter(
                    Certification.token_address == token_address,
                    Certification.signer == signer_address).count() > 0:
                flash('既に情報が登録されています。', 'error')
                return render_template('bond/request_signature.html', form=form)

            # コントラクトに情報を登録する
            try:
                tx = TokenContract.functions.requestSignature(signer_address). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            except ValueError:
                flash('処理に失敗しました。', 'error')
                return render_template('bond/request_signature.html', form=form)

            # DBに情報を登録する
            certification = Certification()
            certification.token_address = token_address
            certification.signer = signer_address
            db.session.add(certification)

            flash('認定依頼を受け付けました。', 'success')
            return redirect(url_for('.setting', token_address=token_address))

        else:  # Validation Error
            flash_errors(form)
            return render_template('bond/request_signature.html', form=form)

    else:  # GET
        form.token_address.data = token_address
        form.signer.data = ''
        return render_template('bond/request_signature.html', form=form)


####################################################
# [債券]公開
####################################################
@bond.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('bond/release')
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
        tx = ListContract.functions.register(token_address, 'IbetStraightBond'). \
            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
    except ValueError:
        flash('既に公開されています。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.list'))


####################################################
# [債券]償還
####################################################
@bond.route('/redeem', methods=['POST'])
@login_required
def redeem():
    logger.info('bond/redeem')

    # Tokenコントラクト接続
    token_address = request.form.get('token_address')
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    try:
        tx = TokenContract.functions.redeem(). \
            buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
    except ValueError:
        flash('償還処理に失敗しました。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('償還処理中です。完了までに数分程かかることがあります。', 'success')
    return redirect(url_for('.setting', token_address=token_address))


####################################################
# [債券]追加発行
####################################################
@bond.route('/add_supply/<string:token_address>', methods=['GET', 'POST'])
@login_required
def add_supply(token_address):
    logger.info('bond/add_supply')

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    form = AddSupplyForm()
    form.token_address.data = token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.total_supply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            try:
                tx = TokenContract.functions.issueFrom(session['eth_account'], Config.ZERO_ADDRESS, form.amount.data). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            except Exception as e:
                logger.error(e)
                flash('処理に失敗しました。', 'error')
                return render_template(
                    'bond/add_supply.html',
                    form=form,
                    token_address=token_address,
                    token_name=name
                )
            flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template(
                'bond/add_supply.html',
                form=form,
                token_address=token_address,
                token_name=name
            )
    else:  # GET
        return render_template(
            'bond/add_supply.html',
            form=form,
            token_address=token_address,
            token_name=name
        )


####################################################
# [債券]保有一覧
####################################################
@bond.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('bond/positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(
        template_id=Config.TEMPLATE_ID_SB,
        admin_address=session['eth_account'].lower()
    ).all()

    position_list = []
    for row in tokens:
        owner = to_checksum_address(row.admin_address)
        if row.token_address is not None:
            try:
                # Tokenコントラクトに接続
                TokenContract = web3.eth.contract(
                    address=row.token_address,
                    abi=json.loads(row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                )

                # Exchange
                token_exchange_address = TokenContract.functions.tradableExchange().call()
                ExchangeContract = ContractUtils.get_contract('IbetStraightBondExchange', token_exchange_address)

                # トークン名称
                name = TokenContract.functions.name().call()

                # トークン略称
                symbol = TokenContract.functions.symbol().call()

                # 総発行量
                total_supply = TokenContract.functions.totalSupply().call()

                # 残高
                balance = TokenContract.functions.balanceOf(owner).call()

                # 償還状況
                is_redeemed = TokenContract.functions.isRedeemed().call()

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
                    filter(Order.amount > 0). \
                    first()
                if order is not None:
                    on_sale = True
                    order_id = order.order_id
                    order_price = order.price
                else:
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
                    'order_id': order_id,
                    'is_redeemed': is_redeemed
                })
            except Exception as e:
                logger.error(e)
                continue

    return render_template('bond/positions.html', position_list=position_list)


####################################################
# [債券]売出
####################################################
@bond.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('bond/sell')
    form = SellTokenForm()

    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    faceValue = TokenContract.functions.faceValue().call()
    interestRate = TokenContract.functions.interestRate().call() * 0.0001
    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = \
        json.loads(interestPaymentDate_string.replace("'", '"').replace('True', 'true').replace('False', 'false')) \
            if interestPaymentDate_string else default_interest_payment_date()
    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionValue = TokenContract.functions.redemptionValue().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnDetails = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()
    memo = TokenContract.functions.memo().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()

    owner = session['eth_account']
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            # PersonalInfo Contract
            personalinfo_address = TokenContract.functions.personalInfoAddress().call()
            PersonalInfoContract = ContractUtils.get_contract(
                'PersonalInfo', personalinfo_address)

            # PaymentGateway Contract
            issuer = Issuer.query.get(session['issuer_id'])
            pg_address = issuer.payment_gateway_contract_address
            PaymentGatewayContract = ContractUtils.get_contract('PaymentGateway', pg_address)

            eth_account = session['eth_account']
            agent_account = issuer.agent_address

            if PersonalInfoContract.functions.isRegistered(eth_account, eth_account).call() == False:
                flash('発行体情報が未登録です。', 'error')
                return redirect(url_for('.sell', token_address=token_address))
            elif PaymentGatewayContract.functions.accountApproved(eth_account, agent_account).call() == False:
                flash('銀行口座情報が未登録です。', 'error')
                return redirect(url_for('.sell', token_address=token_address))
            else:
                # DEXコントラクトへのDeposit
                tx = TokenContract.functions.transfer(tradableExchange, balance). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])

                # 売り注文実行
                ExchangeContract = ContractUtils.get_contract('IbetStraightBondExchange', tradableExchange)
                tx = ExchangeContract.functions. \
                    createOrder(token_address, balance, form.sellPrice.data, False, agent_account). \
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
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        map_interest_payment_date(form, interestPaymentDate)
        form.redemptionDate.data = redemptionDate
        form.redemptionValue.data = redemptionValue
        form.returnDate.data = returnDate
        form.returnDetails.data = returnDetails
        form.purpose.data = purpose
        form.memo.data = memo
        form.tradableExchange.data = tradableExchange
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template(
            'bond/sell.html',
            token_address=token_address,
            token_name=name,
            form=form
        )


####################################################
# [債券]売出停止
####################################################
@bond.route('/cancel_order/<string:token_address>/<int:order_id>', methods=['GET', 'POST'])
@login_required
def cancel_order(token_address, order_id):
    logger.info('bond/cancel_order')
    form = CancelOrderForm()

    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    # Exchangeコントラクトに接続
    token_exchange_address = TokenContract.functions.tradableExchange().call()
    ExchangeContract = ContractUtils.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

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
        # 注文情報を取得する
        orderBook = ExchangeContract.functions.getOrder(order_id).call()
        token_address = orderBook[1]
        amount = orderBook[2]
        price = orderBook[3]

        # トークンの商品名、略称、総発行量を取得する
        name = TokenContract.functions.name().call()
        symbol = TokenContract.functions.symbol().call()
        totalSupply = TokenContract.functions.totalSupply().call()
        faceValue = TokenContract.functions.faceValue().call()

        form.order_id.data = order_id
        form.token_address.data = token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.amount.data = amount
        form.faceValue.data = faceValue
        form.price.data = price
        return render_template('bond/cancel_order.html', form=form)


####################################################
# [債券]募集申込開始/停止
####################################################
@bond.route('/start_initial_offering', methods=['POST'])
@login_required
def start_initial_offering():
    logger.info('bond/start_initial_offering')
    token_address = request.form.get('token_address')
    _set_offering_status(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@bond.route('/stop_initial_offering', methods=['POST'])
@login_required
def stop_initial_offering():
    logger.info('bond/stop_initial_offering')
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
    logger.info('bond/set_initial_offering_status')

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


####################################################
# [債券]募集申込一覧
####################################################
# 申込一覧画面
@bond.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info('bond/applications')
    return render_template(
        'bond/applications.html',
        token_address=token_address,
    )


# 申込者リストCSVダウンロード
@bond.route('/applications_csv_download', methods=['POST'])
@login_required
def applications_csv_download():
    logger.info('bond/applications_csv_download')

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
        'requested_amount,' + \
        'allot_amount,' + \
        'balance\n'
    f.write(data_header)

    for item in application:
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + item["account_address"] + ',' + \
            item["account_name"] + ',' + item["account_email_address"] + ',' + item["data"] + ',' + \
            str(item["requested_amount"]) + ',' + str(item["allotted_amount"]) + ',' + \
            str(item["balance"]) + '\n'
        f.write(data_row)

    now = datetime.now(tz=JST)
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis', 'ignore')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = \
        'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") + 'bond_applications_list.csv'
    return res


# 申込一覧取得
@bond.route('/get_applications/<string:token_address>', methods=['GET'])
@login_required
def get_applications(token_address):
    # Tokenコントラクト接続
    TokenContract = TokenUtils.get_contract(token_address, session['eth_account'])

    # RSA秘密鍵取得
    issuer = Issuer.query.get(session['issuer_id'])
    cipher = None
    try:
        key = RSA.importKey(issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except Exception as err:
        logger.error(f"Cannot open the private key: {err}")

    # PersonalInfoコントラクト接続
    personal_info_contract_address = TokenContract.functions.personalInfoAddress().call()
    PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', personal_info_contract_address)

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
        # 個人情報参照
        encrypted_info = PersonalInfoContract.functions. \
            personal_info(account_address, session['eth_account']).call()[2]
        account_name = ''
        account_email_address = ''
        if encrypted_info == '' or cipher is None:
            pass
        else:
            try:
                # 個人情報を復号
                ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                # NOTE:
                # JavaScriptでRSA暗号化する際に、先頭が0x00の場合は00を削った状態でデータが連携される。
                # そのままdecryptすると、ValueError（Ciphertext with incorrect length）になるため、
                # 先頭に再度00を加えて、decryptを行う。
                if len(ciphertext) == 1279:
                    hex_fixed = "00" + ciphertext.hex()
                    ciphertext = base64.b16decode(hex_fixed.upper())
                message = cipher.decrypt(ciphertext)
                personal_info_json = json.loads(message)

                # 氏名
                if 'name' in personal_info_json:
                    account_name = personal_info_json['name']
                # Eメールアドレス
                if 'email' in personal_info_json:
                    account_email_address = personal_info_json['email']
            except Exception as err:
                logger.error(f"Failed to decrypt: {err}")

        application_data = TokenContract.functions.applications(account_address).call()
        balance = TokenContract.functions.balanceOf(to_checksum_address(account_address)).call()
        application = {
            'account_address': account_address,
            'account_name': account_name,
            'account_email_address': account_email_address,
            'requested_amount': application_data[0],
            'allotted_amount': application_data[1],
            'data': application_data[2],
            'balance': balance
        }
        applications.append(application)

    return jsonify(applications)


####################################################
# [債券]割当登録
####################################################
@bond.route('/allot/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def allot(token_address, account_address):
    logger.info('bond/allot')

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
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            except Exception as e:
                logger.error(e)
                flash('処理に失敗しました。', 'error')
                return render_template(
                    'bond/allot.html',
                    token_address=token_address, account_address=account_address, form=form
                )
            # NOTE: 募集申込一覧が非同期で更新されるため、5秒待つ
            time.sleep(5)
            flash('処理を受け付けました。', 'success')
            return redirect(url_for('.applications', token_address=token_address))
        else:
            flash_errors(form)
            return render_template(
                'bond/allot.html',
                token_address=token_address, account_address=account_address, form=form
            )
    else:  # GET
        return render_template(
            'bond/allot.html',
            token_address=token_address, account_address=account_address, form=form
        )


####################################################
# [債券]権利移転（募集申込）
####################################################
@bond.route('/transfer_allotment/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def transfer_allotment(token_address, account_address):
    logger.info('bond/transfer_allotment')

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
            amount = int(form.amount.data)
            balance = TokenContract.functions.balanceOf(to_checksum_address(session['eth_account'])).call()
            # 残高超チェック
            if amount > balance:
                flash('移転数量が保有残高を超えています。', 'error')
                return render_template(
                    'bond/transfer_allotment.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )
            # 移転処理
            from_address = session['eth_account']
            to_address = to_checksum_address(account_address)
            try:
                tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                    buildTransaction({'from': session['eth_account'], 'gas': Config.TX_GAS_LIMIT})
                ContractUtils.send_transaction(transaction=tx, eth_account=session['eth_account'])
            except Exception as e:
                logger.exception(e)
                flash('処理に失敗しました。', 'error')
                return render_template(
                    'bond/transfer_allotment.html',
                    token_address=token_address, account_address=account_address, form=form
                )
            # NOTE: 募集申込一覧が非同期で更新されるため、5秒待つ
            time.sleep(5)
            flash('処理を受け付けました。', 'success')
            return redirect(url_for('.applications', token_address=token_address))
        else:
            flash_errors(form)
            return render_template(
                'bond/transfer_allotment.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        return render_template(
            'bond/transfer_allotment.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


# トークン追跡
@bond.route('/token/track/<string:token_address>', methods=['GET'])
@login_required
def token_tracker(token_address):
    logger.info('bond/token_tracker')

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
            block_timestamp = datetime.fromtimestamp(row.block_timestamp.timestamp(), JST). \
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
            logger.error(e)
            pass

    return render_template(
        'bond/token_tracker.html',
        token_address=token_address,
        track=track
    )


#################################################
# 原簿管理者情報の登録
#################################################
@bond.route('/ledger_administrator', methods=['GET', 'POST'])
@login_required
def ledger_administrator():
    logger.info('bond/ledger_administrator')

    form = LedgerAdministratorForm()

    ##############################
    # POST
    ##############################
    if request.method == "POST":
        if form.validate():
            record = LedgerAdministrator.query. \
                filter(LedgerAdministrator.eth_account == session["eth_account"]). \
                first()
            if record is None:
                record = LedgerAdministrator()
                record.eth_account = session["eth_account"]
                record.name = form.name.data
                record.address = form.address.data
                record.location = form.location.data
                db.session.add(record)
            else:
                record.name = form.name.data
                record.address = form.address.data
                record.location = form.location.data
            db.session.commit()
            flash('登録処理が完了しました。', 'success')
        else:
            flash_errors(form)

        return render_template('bond/ledger_administrator.html', form=form)

    ##############################
    # GET
    ##############################
    if request.method == "GET":
        record = LedgerAdministrator.query. \
            filter(LedgerAdministrator.eth_account == session['eth_account']). \
            first()
        if record is not None:
            form.name.data = record.name
            form.address.data = record.address
            form.location.data = record.location
        else:
            form.name.data = ""
            form.address.data = ""
            form.location.data = ""

        return render_template('bond/ledger_administrator.html', form=form)


#################################################
# 原簿履歴
#################################################
@bond.route('/ledger_history/<string:token_address>', methods=['GET'])
@login_required
def ledger_history(token_address: str):
    logger.info('bond/ledger_history')

    # アドレスフォーマットチェック
    if not Web3.isAddress(token_address):
        abort(404)

    return render_template('bond/ledger_history.html', token_address=token_address)


# 原簿履歴取得
@bond.route('/get_ledger_history/<string:token_address>', methods=['GET'])
@login_required
def get_ledger_history(token_address):
    logger.info('bond/get_ledger_history')

    # アドレスフォーマットチェック
    if not Web3.isAddress(token_address):
        abort(404)

    # 発行体が管理するトークンであることをチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    records = BondLedger.query. \
        filter(BondLedger.token_address == token_address). \
        order_by(desc(BondLedger.created)). \
        all()

    ledgers = []
    for record in records:
        created_jst = record.created.replace(tzinfo=timezone.utc).astimezone(JST)
        created_formatted = created_jst.strftime("%Y/%m/%d %H:%M:%S %z")
        file_name = f'{created_jst.strftime("%Y%m%d%H%M%S")}bond_ledger.json'
        ledgers.append({
            'id': record.id,
            'token_address': record.token_address,
            'created': created_formatted,
            'file_name': file_name
        })

    return jsonify(ledgers)


# 原簿ダウンロード
@bond.route('/ledger_download', methods=['POST'])
@login_required
def ledger_download():
    logger.info('bond/ledger_download')

    token_address = request.form.get('token_address')
    ledger_id = request.form.get('ledger_id')

    # 発行体が管理するトークンであることをチェック
    token = Token.query. \
        filter(Token.token_address == token_address). \
        filter(Token.admin_address == session['eth_account'].lower()). \
        first()
    if token is None:
        abort(404)

    # 原簿情報の取得
    record = BondLedger.query. \
        filter(BondLedger.id == ledger_id). \
        filter(BondLedger.token_address == token_address). \
        first()
    if record is None:
        abort(404)

    created = record.created.replace(tzinfo=timezone.utc).astimezone(JST)  # JSTに変換
    res = make_response()
    res.data = record.ledger
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = f"attachment; filename={created.strftime('%Y%m%d%H%M%S')}bond_ledger.json"
    return res


####################################################
# 権限エラー
####################################################
@bond.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')
