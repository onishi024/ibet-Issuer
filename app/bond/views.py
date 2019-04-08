# -*- coding:utf-8 -*-
import datetime
import traceback
from base64 import b64encode

from flask import request, redirect, url_for, flash
from flask import render_template
from flask_login import login_required

from . import bond
from .. import db
from ..util import *
from ..models import Token, Certification, Bank
from .forms import *
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

# 債券トークンの保有者一覧、token_nameを返す
def get_holders_bond(token_address):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    # Bond Token Contract
    # Note: token_addressに対して、Bondトークンのものであるかはチェックしていない。
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').\
        replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # Straight-Bond Exchange Contract
    token_exchange_address = Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

    # PersonalInfo Contract
    personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
    PersonalInfoContract = \
        Contract.get_contract('PersonalInfo', personalinfo_address)

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

    # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        commitment = ExchangeContract.functions.\
            commitments(account_address,token_address).call()
        if balance > 0 or commitment > 0:
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
                'commitment':commitment
            }
            holders.append(holder)

    return holders, token_name

####################################################
# [債券]発行済一覧
####################################################
@bond.route('/list', methods=['GET'])
@login_required
def list():
    logger.info('list')

    # 発行済トークンの情報をDBから取得する
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()

    token_list = []
    for row in tokens:
        try:
            is_redeemed = False

            # トークンがデプロイ済みの場合、トークン情報を取得する
            if row.token_address == None:
                name = '<処理中>'
                symbol = '<処理中>'
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
                is_redeemed = TokenContract.functions.isRedeemed().call()

            token_list.append({
                'name':name,
                'symbol':symbol,
                'created':row.created,
                'tx_hash':row.tx_hash,
                'token_address':row.token_address,
                'is_redeemed':is_redeemed
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
    logger.info('holders')
    holders, token_name = get_holders_bond(token_address)
    return render_template('bond/holders.html', \
        holders=holders, token_address=token_address, token_name=token_name)

####################################################
# [債券]保有者移転
####################################################
@bond.route(
    '/transfer_ownership/<string:token_address>/<string:account_address>',
    methods=['GET','POST'])
@login_required
def transfer_ownership(token_address, account_address):
    logger.info('bond/transfer_ownership')

    # アドレスフォーマットのチェック
    if not Web3.isAddress(account_address) or not Web3.isAddress(token_address):
        abort(404)

    # ABI参照
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(
        token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    # 残高参照
    balance = TokenContract.functions.\
        balanceOf(to_checksum_address(account_address)).call()

    form = TransferOwnershipForm()
    if request.method == 'POST':
        if form.validate():
            from_address = to_checksum_address(account_address)
            to_address = to_checksum_address(form.to_address.data)
            amount = int(form.amount.data)

            if amount > balance:
                flash('移転数量が残高を超えています。','error')
                form.from_address.data = from_address
                return render_template(
                    'bond/transfer_ownership.html',
                    token_address = token_address,
                    account_address = account_address,
                    form = form
                )

            eth_unlock_account()
            token_exchange_address = Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS
            ExchangeContract = Contract.get_contract(
                'IbetStraightBondExchange', token_exchange_address)

            deposit_gas = TokenContract.estimateGas().\
                transferFrom(from_address, token_exchange_address, amount)
            TokenContract.functions.\
                transferFrom(from_address, token_exchange_address, amount).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':deposit_gas})

            transfer_gas = ExchangeContract.estimateGas().\
                transfer(to_checksum_address(token_address), to_address, amount)
            txid = ExchangeContract.functions.\
                transfer(to_checksum_address(token_address), to_address, amount).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':transfer_gas})

            tx = web3.eth.waitForTransactionReceipt(txid)
            return redirect(url_for('.holders', token_address=token_address))
        else:
            flash_errors(form)
            form.from_address.data = account_address
            return render_template(
                'bond/transfer_ownership.html',
                token_address = token_address,
                account_address = account_address,
                form = form
            )
    else: # GET
        form.from_address.data = account_address
        form.to_address.data = ''
        form.amount.data = balance
        return render_template(
            'bond/transfer_ownership.html',
            token_address = token_address,
            account_address = account_address,
            form = form
        )

####################################################
# [債券]保有者詳細
####################################################
@bond.route('/holder/<string:token_address>/<string:account_address>', methods=['GET'])
@login_required
def holder(token_address, account_address):
    logger.info('holder')
    personal_info = get_holder(token_address, account_address)
    return render_template(
        'bond/holder.html',
        personal_info=personal_info,
        token_address=token_address
    )

####################################################
# [債券]設定内容修正
####################################################
@bond.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('bond.setting')
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').\
        replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    faceValue = TokenContract.functions.faceValue().call()
    interestRate = TokenContract.functions.interestRate().call() * 0.001
    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = json.loads(
        interestPaymentDate_string.replace("'", '"').\
            replace('True', 'true').replace('False', 'false'))
    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()
    memo = TokenContract.functions.memo().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()
    image_1 = TokenContract.functions.getImageURL(0).call()
    image_2 = TokenContract.functions.getImageURL(1).call()
    image_3 = TokenContract.functions.getImageURL(2).call()

    # TokenList登録状態取得
    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract(
        'TokenList', list_contract_address)
    token_struct = ListContract.functions.getTokenByAddress(token_address).call()
    isRelease = False
    if token_struct[0] == token_address:
        isRelease = True

    # 第三者認定（Sign）のイベント情報を検索する
    signatures = []
    event_filter_sign = TokenContract.eventFilter(
        'Sign', {
            'filter':{},
            'fromBlock':'earliest'
        }
    )
    try:
        entries_sign = event_filter_sign.get_all_entries()
    except:
        entries_sign = []
    for entry in entries_sign:
        if TokenContract.functions.\
            signatures(to_checksum_address(entry['args']['signer'])).call() == 2:
            signatures.append(entry['args']['signer'])

    form = SettingForm()
    if request.method == 'POST':
        if form.validate(): # Validationチェック
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。','error')
                form.token_address.data = token.token_address
                form.name.data = name
                form.symbol.data = symbol
                form.totalSupply.data = totalSupply
                form.faceValue.data = faceValue
                form.interestRate.data = interestRate
                set_interestPaymentDate(form, interestPaymentDate)
                form.redemptionDate.data = redemptionDate
                form.redemptionAmount.data = redemptionAmount
                form.returnDate.data = returnDate
                form.returnAmount.data = returnAmount
                form.purpose.data = purpose
                form.memo.data = memo
                form.abi.data = token.abi
                form.bytecode.data = token.bytecode
                return render_template(
                    'bond/setting.html',
                    form=form, token_address = token_address,
                    token_name = name, isRelease = isRelease ,
                    signatures = signatures
                )

            eth_unlock_account()

            if form.image_1.data != image_1:
                gas = TokenContract.estimateGas().setImageURL(0, form.image_1.data)
                TokenContract.functions.setImageURL(0, form.image_1.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            if form.image_2.data != image_2:
                gas = TokenContract.estimateGas().setImageURL(1, form.image_2.data)
                TokenContract.functions.setImageURL(1, form.image_2.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            if form.image_3.data != image_3:
                gas = TokenContract.estimateGas().setImageURL(2, form.image_3.data)
                TokenContract.functions.setImageURL(2, form.image_3.data).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            if form.tradableExchange.data != tradableExchange:
                gas = TokenContract.estimateGas().\
                    setTradableExchange(to_checksum_address(form.tradableExchange.data))
                TokenContract.functions.\
                    setTradableExchange(to_checksum_address(form.tradableExchange.data)).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            flash('設定変更を受け付けました。変更完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            form.token_address.data = token.token_address
            form.name.data = name
            form.symbol.data = symbol
            form.totalSupply.data = totalSupply
            form.faceValue.data = faceValue
            form.interestRate.data = interestRate
            set_interestPaymentDate(form, interestPaymentDate)
            form.redemptionDate.data = redemptionDate
            form.redemptionAmount.data = redemptionAmount
            form.returnDate.data = returnDate
            form.returnAmount.data = returnAmount
            form.purpose.data = purpose
            form.memo.data = memo
            form.abi.data = token.abi
            form.bytecode.data = token.bytecode
            return render_template(
                'bond/setting.html',
                form=form, token_address = token_address,
                token_name = name, isRelease = isRelease ,
                signatures = signatures
            )
    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        set_interestPaymentDate(form, interestPaymentDate)
        form.redemptionDate.data = redemptionDate
        form.redemptionAmount.data = redemptionAmount
        form.returnDate.data = returnDate
        form.returnAmount.data = returnAmount
        form.purpose.data = purpose
        form.memo.data = memo
        form.image_1.data = image_1
        form.image_2.data = image_2
        form.image_3.data = image_3
        form.tradableExchange.data = tradableExchange
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template(
            'bond/setting.html',
            form=form,
            token_address = token_address,
            token_name = name,
            isRelease = isRelease,
            signatures = signatures
        )

####################################################
# [債券]第三者認定申請
####################################################
@bond.route('/request_signature/<string:token_address>', methods=['GET','POST'])
@login_required
def request_signature(token_address):
    logger.info('bond.request_signature')

    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    eth_unlock_account()

    form = RequestSignatureForm()
    if request.method == 'POST':
        if form.validate():

            # 指定した認定者のアドレスが有効なアドレスであるかどうかをチェックする
            if not Web3.isAddress(form.signer.data):
                flash('有効なアドレスではありません。','error')
                return render_template('bond/request_signature.html', form=form)

            signer_address = to_checksum_address(form.signer.data)

            # DBに既に情報が登録されている場合はエラーを返す
            if Certification.query.filter(
                Certification.token_address==token_address,
                Certification.signer==signer_address).count() > 0:
                flash('既に情報が登録されています。', 'error')
                return render_template('bond/request_signature.html', form=form)

            # コントラクトに情報を登録する
            try:
                gas = TokenContract.estimateGas().requestSignature(signer_address)
                txid = TokenContract.functions.\
                    requestSignature(signer_address).\
                    transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
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

        else: # Validation Error
            flash_errors(form)
            return render_template('bond/request_signature.html', form=form)

    else: #GET
        form.token_address.data = token_address
        form.signer.data = ''
        return render_template('bond/request_signature.html', form=form)

####################################################
# [債券]公開
####################################################
@bond.route('/release', methods=['POST'])
@login_required
def release():
    logger.info('bond.release')
    token_address = request.form.get('token_address')

    list_contract_address = Config.TOKEN_LIST_CONTRACT_ADDRESS
    ListContract = Contract.get_contract(
        'TokenList', list_contract_address)

    eth_unlock_account()

    try:
        gas = ListContract.estimateGas().\
            register(token_address, 'IbetStraightBond')
        register_txid = ListContract.functions.\
            register(token_address, 'IbetStraightBond').\
            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
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
    logger.info('bond.redeem')

    token_address = request.form.get('token_address')
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= to_checksum_address(token.token_address),
        abi = token_abi
    )

    eth_unlock_account()

    try:
        gas = TokenContract.estimateGas().redeem()
        txid = TokenContract.functions.redeem().\
            transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
    except ValueError:
        flash('償還処理に失敗しました。', 'error')
        return redirect(url_for('.setting', token_address=token_address))

    flash('償還処理中です。完了までに数分程かかることがあります。', 'success')
    return redirect(url_for('.setting', token_address=token_address))

####################################################
# [債券]新規発行
####################################################
@bond.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('bond.issue')
    form = IssueForm()
    if request.method == 'POST':
        if form.validate():
            if not Web3.isAddress(form.tradableExchange.data):
                flash('DEXアドレスは有効なアドレスではありません。','error')
                return render_template('bond/issue.html', form=form)

            eth_unlock_account()

            ####### トークン発行処理 #######
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

            arguments = [
                form.name.data,
                form.symbol.data,
                form.totalSupply.data,
                to_checksum_address(form.tradableExchange.data),
                form.faceValue.data,
                int(form.interestRate.data * 1000),
                interestPaymentDate_string,
                form.redemptionDate.data,
                form.redemptionAmount.data,
                form.returnDate.data,
                form.returnAmount.data,
                form.purpose.data,
                form.memo.data
            ]
            _, bytecode, bytecode_runtime = Contract.get_contract_info('IbetStraightBond')
            contract_address, abi, tx_hash = \
                Contract.deploy_contract(
                    'IbetStraightBond', arguments, Config.ETH_ACCOUNT)

            token = Token()
            token.template_id = Config.TEMPLATE_ID_SB
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(abi)
            token.bytecode = bytecode
            token.bytecode_runtime = bytecode_runtime
            db.session.add(token)

            flash('新規発行を受け付けました。発行完了までに数分程かかることがあります。', 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('bond/issue.html', form=form)
    else: # GET
        return render_template('bond/issue.html', form=form)

####################################################
# [債券]保有一覧
####################################################
@bond.route('/positions', methods=['GET'])
@login_required
def positions():
    logger.info('bond.positions')

    # 自社が発行したトークンの一覧を取得
    tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_SB).all()

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

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
                    'token_address':row.token_address,
                    'name':name,
                    'symbol':symbol,
                    'totalSupply':totalSupply,
                    'balance':balance,
                    'created':row.created,
                    'commitment':commitment,
                    'on_sale':on_sale,
                })

    return render_template('bond/positions.html', position_list=position_list)

####################################################
# [債券]売出
####################################################
@bond.route('/sell/<string:token_address>', methods=['GET', 'POST'])
@login_required
def sell(token_address):
    logger.info('bond.sell')
    form = SellTokenForm()

    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').\
        replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi
    )

    name = TokenContract.functions.name().call()
    symbol = TokenContract.functions.symbol().call()
    totalSupply = TokenContract.functions.totalSupply().call()
    faceValue = TokenContract.functions.faceValue().call()
    interestRate = TokenContract.functions.interestRate().call() * 0.001
    interestPaymentDate_string = TokenContract.functions.interestPaymentDate().call()
    interestPaymentDate = json.loads(
        interestPaymentDate_string.replace("'", '"').\
            replace('True', 'true').replace('False', 'false'))
    redemptionDate = TokenContract.functions.redemptionDate().call()
    redemptionAmount = TokenContract.functions.redemptionAmount().call()
    returnDate = TokenContract.functions.returnDate().call()
    returnAmount = TokenContract.functions.returnAmount().call()
    purpose = TokenContract.functions.purpose().call()
    memo = TokenContract.functions.memo().call()
    tradableExchange = TokenContract.functions.tradableExchange().call()

    owner = Config.ETH_ACCOUNT
    balance = TokenContract.functions.balanceOf(owner).call()

    if request.method == 'POST':
        if form.validate():
            # PersonalInfo Contract
            personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
            PersonalInfoContract = Contract.get_contract(
                'PersonalInfo', personalinfo_address)

            # PaymentGateway Contract
            pg_address = Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS
            PaymentGatewayContract = Contract.get_contract('PaymentGateway', pg_address)

            eth_account = Config.ETH_ACCOUNT
            agent_account = Config.AGENT_ADDRESS

            if PersonalInfoContract.functions.isRegistered(eth_account,eth_account).call() == False:
                flash('発行体情報が未登録です。', 'error')
                return redirect(url_for('.sell', token_address=token_address))
            elif PaymentGatewayContract.functions.accountApproved(eth_account, agent_account).call() == False:
                flash('銀行口座情報が未登録です。', 'error')
                return redirect(url_for('.sell', token_address=token_address))
            else:
                eth_unlock_account()
                token_exchange_address = Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS
                agent_address = Config.AGENT_ADDRESS

                deposit_gas = TokenContract.estimateGas().transfer(token_exchange_address, balance)
                TokenContract.functions.transfer(token_exchange_address, balance).\
                    transact({'from':eth_account, 'gas':deposit_gas})

                ExchangeContract = Contract.get_contract(
                    'IbetStraightBondExchange', token_exchange_address)
                sell_gas = ExchangeContract.estimateGas().\
                    createOrder(token_address, balance, form.sellPrice.data, False, agent_address)
                txid = ExchangeContract.functions.\
                    createOrder(token_address, balance, form.sellPrice.data, False, agent_address).\
                    transact({'from':eth_account, 'gas':sell_gas})
                tx = web3.eth.waitForTransactionReceipt(txid)
                flash('新規売出を受け付けました。売出開始までに数分程かかることがあります。', 'success')
                return redirect(url_for('.positions'))
        else:
            flash_errors(form)
            return redirect(url_for('.sell', token_address=token_address))

    else: # GET
        form.token_address.data = token.token_address
        form.name.data = name
        form.symbol.data = symbol
        form.totalSupply.data = totalSupply
        form.faceValue.data = faceValue
        form.interestRate.data = interestRate
        set_interestPaymentDate(form, interestPaymentDate)
        form.redemptionDate.data = redemptionDate
        form.redemptionAmount.data = redemptionAmount
        form.returnDate.data = returnDate
        form.returnAmount.data = returnAmount
        form.purpose.data = purpose
        form.memo.data = memo
        form.tradableExchange.data = tradableExchange
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        form.sellPrice.data = None
        return render_template(
            'bond/sell.html',
            token_address = token_address,
            token_name = name,
            form = form
        )

####################################################
# [債券]売出停止
####################################################
@bond.route('/cancel_order/<string:token_address>', methods=['GET', 'POST'])
@login_required
def cancel_order(token_address):
    logger.info('bond.cancel_order')
    form = CancelOrderForm()

    # トークンのABIを取得する
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    # Exchangeコントラクトに接続
    token_exchange_address = Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

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
            txid = ExchangeContract.functions.cancelOrder(order_id).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':gas})
            tx = web3.eth.waitForTransactionReceipt(txid)
            flash('売出停止処理を受け付けました。停止されるまでに数分程かかることがあります。', 'success')
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
# 権限エラー
####################################################
@bond.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')

#+++++++++++++++++++++++++++++++
# Custom Filter
#+++++++++++++++++++++++++++++++
@bond.app_template_filter()
def format_date(date): # date = datetime object.
    if date:
        if isinstance(date, datetime.datetime):
            return date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(date, datetime.date):
            return date.strftime('%Y/%m/%d')
    return ''

@bond.app_template_filter()
def img_convert(icon):
    if icon:
        img = b64encode(icon)
        return img.decode('utf8')
    return None

# 利払日をformにセットする
def set_interestPaymentDate(form, interestPaymentDate):
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
