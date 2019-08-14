# -*- coding:utf-8 -*-
import csv
import io

from flask import request, redirect, url_for, flash, make_response
from flask import render_template
from flask_login import login_required

from . import mrf
from .forms import *
from .. import db
from ..util import *
from ..models import Token, MRFBulkTransfer
from config import Config
from app.contracts import Contract

from logging import getLogger

logger = getLogger('api')

from web3 import Web3
from eth_utils import to_checksum_address
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


# +++++++++++++++++++++++++++++++
# 権限エラー
# +++++++++++++++++++++++++++++++
@mrf.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')


# +++++++++++++++++++++++++++++++
# 新規発行
# +++++++++++++++++++++++++++++++
@mrf.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('mrf.issue')
    form = IssueForm()

    if request.method == 'POST':
        if form.validate():
            # Exchangeコントラクトのアドレスフォーマットチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                return render_template('mrf/issue.html', form=form, form_description=form.description)

            # EOAアンロック
            eth_unlock_account()

            # トークン発行（トークンコントラクトのデプロイ）
            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                to_checksum_address(form.tradableExchange.data),
                form.details.data,
                form.memo.data,
                form.contact_information.data,
                form.privacy_policy.data
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetMRF')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract('IbetMRF', arguments, Config.ETH_ACCOUNT)

            # 発行情報をDBに登録
            token = Token()
            token.template_id = Config.TEMPLATE_ID_MRF
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
            return render_template('mrf/issue.html', form=form, form_description=form.description)
    else:  # GET
        return render_template('mrf/issue.html', form=form, form_description=form.description)


# +++++++++++++++++++++++++++++++
# 発行済一覧
# +++++++++++++++++++++++++++++++
@mrf.route('/list', methods=['GET'])
@login_required
def list():
    logger.info('mrf/list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MRF).all()

    token_list = []
    for row in tokens:
        try:
            # ABI取得
            abi = json.loads(
                row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
            )

            # デプロイ済みの場合　→　トークン情報を取得する
            # デプロイされていない場合　→　「処理中」情報を返す
            if row.token_address is None:
                name = '--'
                symbol = '--'
                status = '--'
                totalSupply = '--'
            else:
                # Token-Contractへの接続
                TokenContract = web3.eth.contract(address=row.token_address, abi=abi)
                # Token-Contractから情報を取得する
                name = TokenContract.functions.name().call()
                symbol = TokenContract.functions.symbol().call()
                status = TokenContract.functions.status().call()
                totalSupply = TokenContract.functions.totalSupply().call()

            # 返り値のリストを作成する
            token_list.append({
                'name': name,
                'symbol': symbol,
                'created': row.created,
                'tx_hash': row.tx_hash,
                'token_address': row.token_address,
                'totalSupply': totalSupply,
                'status': status
            })

        except Exception as e:
            logger.error(e)
            pass

    return render_template('mrf/list.html', tokens=token_list)


# +++++++++++++++++++++++++++++++
# 設定変更
# +++++++++++++++++++++++++++++++
@mrf.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('mrf.setting')

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
    details = TokenContract.functions.details().call()
    memo = TokenContract.functions.memo().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    status = TokenContract.functions.status().call()
    image_1 = TokenContract.functions.getImageURL(0).call()
    image_2 = TokenContract.functions.getImageURL(1).call()
    image_3 = TokenContract.functions.getImageURL(2).call()
    contact_information = TokenContract.functions.contactInformation().call()
    privacy_policy = TokenContract.functions.privacyPolicy().call()

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
                    'mrf/setting.html',
                    form=form, token_address=token_address,
                    status=status, token_name=name
                )

            # アカウントアンロック
            eth_unlock_account()

            # トークン詳細変更
            if form.details.data != details:
                gas = TokenContract.estimateGas().setDetails(form.details.data)
                TokenContract.functions.setDetails(form.details.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

            # メモ欄変更
            if form.memo.data != memo:
                gas = TokenContract.estimateGas().setMemo(form.memo.data)
                TokenContract.functions.setMemo(form.memo.data).transact(
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
                'mrf/setting.html',
                form=form, token_address=token_address,
                status=status, token_name=name
            )
    else:  # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.details.data = details
        form.memo.data = memo
        form.image_1.data = image_1
        form.image_2.data = image_2
        form.image_3.data = image_3
        form.tradableExchange.data = tradableExchange
        form.contact_information.data = contact_information
        form.privacy_policy.data = privacy_policy
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'mrf/setting.html',
            form=form,
            token_address=token_address,
            token_name=name,
            status=status
        )


# +++++++++++++++++++++++++++++++
# 保有者一覧
# +++++++++++++++++++++++++++++++
@mrf.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('mrf/holders')
    return render_template(
        'mrf/holders.html',
        token_address=token_address
    )


# 保有者一覧取得
@mrf.route('/get_holders/<string:token_address>', methods=['GET'])
@login_required
def get_holders(token_address):
    # 個人情報復号化用の秘密鍵
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except Exception as err:
        logger.error(err)
        pass

    # ABI取得
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # トークンコントラクト設定
    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    # PersonalInfoコントラクト設定
    personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personalinfo_address)

    # MRFトークンから発生している"Transfer"のログ情報から
    # 残高が存在している可能性のあるアドレスを抽出する
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

    # アドレスをユニークにする
    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    # トークンのOwner（発行者）のアドレスを取得する
    token_owner = TokenContract.functions.owner().call()
    token_name = TokenContract.functions.name().call()

    # 残高が存在する情報を抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        if balance > 0:
            encrypted_info = PersonalInfoContract.functions. \
                personal_info(account_address, token_owner).call()[2]
            if encrypted_info == '' or cipher == None:
                name = ''
            else:
                ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                try:
                    message = cipher.decrypt(ciphertext)
                    personal_info_json = json.loads(message)
                    name = personal_info_json['name']
                except:
                    name = ''

            holder = {
                'account_address': account_address,
                'name': name,
                'balance': balance
            }
            holders.append(holder)

    return json.dumps(holders)


@mrf.route('/get_token_name/<string:token_address>', methods=['GET'])
@login_required
def get_token_name(token_address):
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    token_name = TokenContract.functions.name().call()

    return json.dumps(token_name)


# +++++++++++++++++++++++++++++++
# 保有者詳細
# +++++++++++++++++++++++++++++++
@mrf.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('mrf/holder')
    personal_info = get_holder(token_address, account_address)
    return render_template(
        'mrf/holder.html',
        personal_info=personal_info,
        token_address=token_address
    )


# +++++++++++++++++++++++++++++++
# 保有者移転
# +++++++++++++++++++++++++++++++
@mrf.route(
    '/transfer_ownership/<string:token_address>/<string:account_address>',
    methods=['GET', 'POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info('mrf/transfer_ownership')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    token_address = to_checksum_address(token_address)
    account_address = to_checksum_address(account_address)

    # ABI参照
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # トークンコントラクト設定
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    # 残高参照
    balance = TokenContract.functions.balanceOf(account_address).call()

    form = TransferOwnershipForm()
    if request.method == 'POST':
        if form.validate():
            from_address = account_address
            to_address = to_checksum_address(form.to_address.data)
            amount = int(form.amount.data)

            # 残高超過チェック
            if amount > balance:
                flash('移転数量が残高を超えています。', 'error')
                form.from_address.data = from_address
                return render_template(
                    'mrf/transfer_ownership.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            # アカウントアンロック
            eth_unlock_account()

            # 移転
            deposit_gas = TokenContract.estimateGas(). \
                transferFrom(from_address, to_address, amount)
            txid = TokenContract.functions. \
                transferFrom(from_address, to_address, amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})
            web3.eth.waitForTransactionReceipt(txid)
            return redirect(url_for('.holders', token_address=token_address))

        else:  # 入力値エラーの場合
            flash_errors(form)
            form.from_address.data = account_address
            return render_template(
                'mrf/transfer_ownership.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )
    else:  # GET
        form.from_address.data = account_address
        form.to_address.data = ''
        form.amount.data = balance
        return render_template(
            'mrf/transfer_ownership.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


# +++++++++++++++++++++++++++++++
# 償却
# +++++++++++++++++++++++++++++++
@mrf.route('/burn/<string:token_address>/<string:account_address>', methods=['GET', 'POST'])
@login_required
def burn(token_address, account_address):
    logger.info('mrf/burn')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    token_address = to_checksum_address(token_address)
    account_address = to_checksum_address(account_address)

    # ABI参照
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # トークンコントラクト設定
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    # 残高参照
    balance = TokenContract.functions.balanceOf(account_address).call()

    form = BurnForm()
    if request.method == 'POST':
        if form.validate():
            burn_amount = int(form.burn_amount.data)

            # 残高超過チェック
            if burn_amount > balance:
                flash('移転数量が残高を超えています。', 'error')
                form.account_address.data = account_address
                form.balance.data = balance
                return render_template(
                    'mrf/burn.html',
                    token_address=token_address,
                    account_address=account_address,
                    form=form
                )

            # アカウントアンロック
            eth_unlock_account()

            # 償却
            deposit_gas = TokenContract.estimateGas(). \
                burn(account_address, burn_amount)
            txid = TokenContract.functions. \
                burn(account_address, burn_amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})
            web3.eth.waitForTransactionReceipt(txid)
            return redirect(url_for('.holders', token_address=token_address))

        else:  # 入力値エラーの場合
            flash_errors(form)
            form.account_address.data = account_address
            form.balance.data = balance
            return render_template(
                'mrf/burn.html',
                token_address=token_address,
                account_address=account_address,
                form=form
            )

    else:  # GET
        form.account_address.data = account_address
        form.balance.data = balance
        return render_template(
            'mrf/burn.html',
            token_address=token_address,
            account_address=account_address,
            form=form
        )


# +++++++++++++++++++++++++++++++
# 追加発行
# +++++++++++++++++++++++++++++++
@mrf.route('/additional_issue/<string:token_address>', methods=['GET', 'POST'])
@login_required
def additional_issue(token_address):
    logger.info('mrf/additional_issue')

    # ABI参照
    token = Token.query.filter(Token.token_address == token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # トークンコントラクト設定
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    form = AdditionalIssueForm()
    form.token_address.data = token.token_address
    name = TokenContract.functions.name().call()
    form.name.data = name
    form.total_supply.data = TokenContract.functions.totalSupply().call()

    if request.method == 'POST':
        if form.validate():
            # アカウントアンロック
            eth_unlock_account()

            # 追加発行
            gas = TokenContract.estimateGas().issue(form.amount.data)
            TokenContract.functions.issue(form.amount.data). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
            flash('追加発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))

        else:  # 入力値エラーの場合
            flash_errors(form)
            return render_template(
                'mrf/additional_issue.html',
                form=form,
                token_address=token_address,
                token_name=name
            )
    else:  # GET
        return render_template(
            'mrf/additional_issue.html',
            form=form,
            token_address=token_address,
            token_name=name
        )


# +++++++++++++++++++++++++++++++
# 有効化/無効化
# +++++++++++++++++++++++++++++++
@mrf.route('/valid', methods=['POST'])
@login_required
def valid():
    logger.info('mrf/valid')
    token_address = request.form.get('token_address')
    setStatus(token_address, True)
    return redirect(url_for('.setting', token_address=token_address))


@mrf.route('/invalid', methods=['POST'])
@login_required
def invalid():
    logger.info('mrf/invalid')
    token_address = request.form.get('token_address')
    setStatus(token_address, False)
    return redirect(url_for('.setting', token_address=token_address))


def setStatus(token_address, isvalid):
    # アカウントアンロック
    eth_unlock_account()

    # ABI参照
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # トークンコントラクト設定
    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    # ステータス変更
    try:
        gas = TokenContract.estimateGas().setStatus(isvalid)
        tx = TokenContract.functions.setStatus(isvalid). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
        web3.eth.waitForTransactionReceipt(tx)
        flash('処理を受け付けました。', 'success')
    except Exception as e:
        logger.error(e)
        flash('更新処理でエラーが発生しました。', 'error')


# +++++++++++++++++++++++++++++++
# 送金履歴
# +++++++++++++++++++++++++++++++
@mrf.route('/transfer_history/<string:token_address>', methods=['GET'])
@login_required
def transfer_history(token_address):
    logger.info('mrf/transfer_history')
    return render_template(
        'mrf/transfer_history.html',
        token_address=token_address
    )


# 送金（譲渡）履歴取得
@mrf.route('/get_transfer_history/<string:token_address>', methods=['GET'])
@login_required
def get_transfer_history(token_address):
    # ABI取得
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
    )

    # トークンコントラクト設定
    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    # MRFトークンから発生している"Transfer"のログ情報を検索
    event_filter = TokenContract.eventFilter(
        'Transfer', {
            'filter': {},
            'fromBlock': 'earliest'
        }
    )
    entries = event_filter.get_all_entries()

    # 送金履歴リストを作成する
    history = []
    for entry in entries:
        blocktime = datetime.fromtimestamp(web3.eth.getBlock(entry["blockNumber"])["timestamp"], JST)
        history.append(
            {
                'block_timestamp': str(blocktime),
                'from_address': entry['args']['from'],
                'to_address': entry['args']['to'],
                'value': entry['args']['value']
            }
        )

    return json.dumps(history)


# 利用履歴リストCSVダウンロード
@mrf.route('/transferred_csv_download', methods=['POST'])
@login_required
def transferred_csv_download():
    logger.info('mrf/transferred_csv_download')

    token_address = request.form.get('token_address')
    token_address, token_name, transfer_list = get_transfer_history(token_address)

    f = io.StringIO()
    for transfer in transfer_list:
        # データ行
        data_row = \
            token_name + ',' + token_address + ',' + transfer["block_timestamp"] + ',' + transfer["from_address"] + \
            ',' + str(transfer["to_address"]) + ',' + str(transfer["value"]) + '\n'
        f.write(data_row)
        logger.info(transfer)

    now = datetime.now()
    res = make_response()
    csvdata = f.getvalue()
    res.data = csvdata.encode('sjis')
    res.headers['Content-Type'] = 'text/plain'
    res.headers['Content-Disposition'] = 'attachment; filename=' + now.strftime("%Y%m%d%H%M%S") + \
        'mrf_transfer_list.csv'
    return res


# +++++++++++++++++++++++++++++++
# 割当（個別）
# +++++++++++++++++++++++++++++++
@mrf.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    logger.info('mrf/transfer')
    form = TransferForm()

    if request.method == 'POST':
        if form.validate():
            # Addressフォーマットチェック（token_address）
            if not Web3.isAddress(form.token_address.data):
                flash('クーポンアドレスは有効なアドレスではありません。', 'error')
                return render_template('mrf/transfer.html', form=form)

            # Addressフォーマットチェック（send_address）
            if not Web3.isAddress(form.to_address.data):
                flash('割当先アドレスは有効なアドレスではありません。', 'error')
                return render_template('mrf/transfer.html', form=form)

            # Tokenコントラクト接続
            token = Token.query. \
                filter(Token.token_address == form.token_address.data).first()
            token_abi = json.loads(
                token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            TokenContract = web3.eth.contract(
                address=token.token_address,
                abi=token_abi
            )

            # 割当処理（発行体アドレス→指定アドレス）
            from_address = Config.ETH_ACCOUNT
            to_address = to_checksum_address(form.to_address.data)
            amount = form.amount.data
            transfer_token(TokenContract, from_address, to_address, amount)

            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return render_template('mrf/transfer.html', form=form)
        else:
            flash_errors(form)
            return render_template('mrf/transfer.html', form=form)
    else:  # GET
        return render_template('mrf/transfer.html', form=form)


# 割当（CSV一括）
@mrf.route('/bulk_transfer', methods=['GET', 'POST'])
@login_required
def bulk_transfer():
    logger.info('mrf/bulk_transfer')
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

            except Exception as e:
                logger.error(e)
                flash('CSVアップロードでエラーが発生しました。', 'error')
                transfer_set = "error"
                return render_template('mrf/bulk_transfer.html', form=form, transfer_set=transfer_set)

            # transfer_rowの構成：[token_address, to_address, amount]
            for transfer_row in transfer_set:
                # Addressフォーマットチェック（token_address）
                if not Web3.isAddress(transfer_row[0]):
                    flash('無効なトークンアドレスが含まれています。', 'error')
                    message = '無効なトークンアドレスが含まれています。' + transfer_row[0]
                    logger.warning(message)
                    return render_template('mrf/bulk_transfer.html', form=form)

                # Addressフォーマットチェック（to_address）
                if not Web3.isAddress(transfer_row[1]):
                    flash('無効な割当先アドレスが含まれています。', 'error')
                    message = '無効な割当先アドレスが含まれています' + transfer_row[1]
                    logger.warning(message)
                    return render_template('mrf/bulk_transfer.html', form=form)

                # amountチェック
                if 100000000 < int(transfer_row[2]):
                    flash('割当量が適切ではありません。', 'error')
                    message = '割当量が適切ではありません' + transfer_row[2]
                    logger.warning(message)
                    return render_template('mrf/bulk_transfer.html', form=form)

                # DB登録処理
                csvtransfer = MRFBulkTransfer()
                csvtransfer.token_address = transfer_row[0]
                csvtransfer.to_address = transfer_row[1]
                csvtransfer.amount = transfer_row[2]
                csvtransfer.transferred = False
                db.session.add(csvtransfer)

            # 全てのデータが正常処理されたらコミットを行う
            db.session.commit()

            flash('処理を受け付けました。割当完了までに数分程かかることがあります。', 'success')
            return render_template('mrf/bulk_transfer.html', form=form, transfer_set=transfer_set)

        else:
            flash_errors(form)
            return render_template('mrf/bulk_transfer.html', form=form, transfer_set=transfer_set)

    else:  # GET
        return render_template('mrf/bulk_transfer.html', form=form)


# サンプルCSVダウンロード
@mrf.route('/sample_csv_download', methods=['POST'])
@login_required
def sample_csv_download():
    logger.info('mrf/sample_csv_download')

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


def transfer_token(TokenContract, from_address, to_address, amount):
    eth_unlock_account()
    transfer_gas = TokenContract.estimateGas(). \
        transferFrom(from_address, to_address, amount)
    tx_hash = TokenContract.functions. \
        transferFrom(from_address, to_address, amount). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': transfer_gas})
    return tx_hash
