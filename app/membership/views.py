# -*- coding:utf-8 -*-
import traceback

from flask import request, redirect, url_for, flash
from flask import render_template
from flask_login import login_required

from . import membership
from .. import db
from ..util import *
from ..models import Token
from .forms import *
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
            if row.token_address == None:
                name = '<処理中>'
                symbol = '<処理中>'
                status = '<処理中>'
                totalSupply = '<処理中>'
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

    return render_template('membership/list.html', tokens=token_list)


####################################################
# [会員権]募集申込一覧
####################################################
@membership.route('/applications/<string:token_address>', methods=['GET'])
@login_required
def applications(token_address):
    logger.info('membership/applications')
    applications, token_name = get_applications(token_address)
    return render_template(
        'membership/applications.html',
        applications=applications,
        token_address=token_address,
        token_name=token_name
    )


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
# [会員権]割当（募集申込）
####################################################
@membership.route(
    '/allocate/<string:token_address>/<string:account_address>',
    methods=['GET', 'POST'])
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
            tx_hash = transfer_token(TokenContract, from_address, to_address, amount)

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


def transfer_token(TokenContract, from_address, to_address, amount):
    eth_unlock_account()
    token_exchange_address = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetMembershipExchange', token_exchange_address)

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
# [会員権]保有者一覧
####################################################
@membership.route('/holders/<string:token_address>', methods=['GET'])
@login_required
def holders(token_address):
    logger.info('membership/holders')
    holders, token_name = get_holders(token_address)
    return render_template(
        'membership/holders.html',
        holders=holders,
        token_address=token_address,
        token_name=token_name
    )


def get_holders(token_address):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token_address,
        abi=token_abi
    )

    # Exchange Contract
    token_exchange_address = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetMembershipExchange', token_exchange_address)

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

    # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        commitment = ExchangeContract.functions. \
            commitments(account_address, token_address).call()
        if balance > 0 or commitment > 0:
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
                'commitment': commitment
            }
            holders.append(holder)

    return holders, token_name


####################################################
# [会員権]保有者移転
####################################################
@membership.route(
    '/transfer_ownership/<string:token_address>/<string:account_address>',
    methods=['GET', 'POST'])
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

            eth_unlock_account()
            token_exchange_address = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
            ExchangeContract = Contract.get_contract(
                'IbetMembershipExchange', token_exchange_address)

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
    return render_template('membership/holder.html', personal_info=personal_info, token_address=token_address)


####################################################
# [会員権]設定内容修正
####################################################
@membership.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('membership.setting')
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
    returnDetails = TokenContract.functions.returnDetails().call()
    expirationDate = TokenContract.functions.expirationDate().call()
    memo = TokenContract.functions.memo().call()
    transferable = str(TokenContract.functions.transferable().call())
    tradableExchange = TokenContract.functions.tradableExchange().call()
    status = TokenContract.functions.status().call()
    image_1 = TokenContract.functions.getImageURL(0).call()
    image_2 = TokenContract.functions.getImageURL(1).call()
    image_3 = TokenContract.functions.getImageURL(2).call()

    try:
        initial_offering_status = TokenContract.functions.initialOfferingStatus().call()
    except:
        initial_offering_status = False

    # TokenList登録状態取得
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract(
        'TokenList', list_contract_address)
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

            eth_unlock_account()

            if form.details.data != details:
                gas = TokenContract.estimateGas().setDetails(form.details.data)
                TokenContract.functions.setDetails(form.details.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
            if form.returnDetails.data != returnDetails:
                gas = TokenContract.estimateGas().setReturnDetails(form.returnDetails.data)
                TokenContract.functions.setReturnDetails(form.returnDetails.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
            if form.expirationDate.data != expirationDate:
                gas = TokenContract.estimateGas().setExpirationDate(form.expirationDate.data)
                TokenContract.functions.setExpirationDate(form.expirationDate.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
            if form.memo.data != memo:
                gas = TokenContract.estimateGas().setMemo(form.memo.data)
                TokenContract.functions.setMemo(form.memo.data).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
            if form.transferable.data != transferable:
                tmpVal = True
                if form.transferable.data == 'False':
                    tmpVal = False
                gas = TokenContract.estimateGas().setTransferable(tmpVal)
                TokenContract.functions.setTransferable(tmpVal).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )
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
            if form.tradableExchange.data != tradableExchange:
                gas = TokenContract.estimateGas().setTradableExchange(to_checksum_address(form.tradableExchange.data))
                TokenContract.functions.setTradableExchange(
                    to_checksum_address(form.tradableExchange.data)).transact(
                    {'from': Config.ETH_ACCOUNT, 'gas': gas}
                )

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
        form.returnDetails.data = returnDetails
        form.expirationDate.data = expirationDate
        form.memo.data = memo
        form.transferable.data = transferable
        form.image_1.data = image_1
        form.image_2.data = image_2
        form.image_3.data = image_3
        form.tradableExchange.data = tradableExchange
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
        register_txid = ListContract.functions. \
            register(token_address, 'IbetMembership'). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
    except ValueError:
        flash('既に公開されています。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.list'))


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
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。', 'error')
                return render_template('membership/issue.html', form=form)

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
                form.returnDetails.data,
                form.expirationDate.data,
                form.memo.data,
                tmpVal
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetMembership')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract('IbetMembership', arguments, Config.ETH_ACCOUNT)

            token = Token()
            token.template_id = Config.TEMPLATE_ID_MEMBERSHIP
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            ####### 画像URL登録処理 #######
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
            return render_template('membership/issue.html', form=form)
    else:  # GET
        return render_template('membership/issue.html', form=form)


####################################################
# [会員権]保有一覧（売出管理画面）
####################################################
@membership.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('membership/positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_MEMBERSHIP).all()

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetMembershipExchange', token_exchange_address)

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
                commitments(owner, row.token_address).call()

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
    returnDetails = TokenContract.functions.returnDetails().call()
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
        form.returnDetails.data = returnDetails
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
@membership.route('/cancel_order/<string:token_address>', methods=['GET', 'POST'])
@login_required
def cancel_order(token_address):
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
        canceled = ExchangeContract.functions.orderBook(order_id_tmp).call()[6]
        if canceled == False:
            order_id = order_id_tmp

    # 注文情報を取得する
    orderBook = ExchangeContract.functions.orderBook(order_id).call()
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
            tx = web3.eth.waitForTransactionReceipt(txid)
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
            tx = TokenContract.functions.issue(form.addSupply.data). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
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

    gas = TokenContract.estimateGas().setStatus(isvalid)
    tx = TokenContract.functions.setStatus(isvalid). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx)

    flash('処理を受け付けました。', 'success')

####################################################
# [会員権]募集申込開始/停止
####################################################
@membership.route('/start_initial_offering', methods=['POST'])
@login_required
def start_initial_offering():
    logger.info('membership/start_initial_offering')
    token_address = request.form.get('token_address')
    transact_status = set_initial_offering_status(token_address, True)
    if transact_status:
        return redirect(url_for('.list'))
    else:
        return redirect(url_for('.setting', token_address=token_address))


@membership.route('/stop_initial_offering', methods=['POST'])
@login_required
def stop_initial_offering():
    logger.info('membership/stop_initial_offering')
    token_address = request.form.get('token_address')
    transact_status = set_initial_offering_status(token_address, False)
    if transact_status:
        return redirect(url_for('.list'))
    else:
        return redirect(url_for('.setting', token_address=token_address))


def set_initial_offering_status(token_address, status):
    eth_unlock_account()
    token = Token.query.filter(Token.token_address == token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address=token.token_address,
        abi=token_abi
    )

    transact_status = True
    try:
        gas = TokenContract.estimateGas().setInitialOfferingStatus(status)
        tx = TokenContract.functions.setInitialOfferingStatus(status). \
            transact({'from': Config.ETH_ACCOUNT, 'gas': gas})
    except:
        flash('募集申込ステータスの更新処理でエラーが発生しました。', 'error')
        transact_status = False
        return transact_status

    flash('処理を受け付けました。完了までに数分程かかることがあります。', 'success')
    return transact_status


####################################################
# [会員権]権限エラー
####################################################
@membership.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')
