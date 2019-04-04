# -*- coding:utf-8 -*-
import secrets
import datetime
import requests

from flask import request, redirect, url_for, flash, render_template
from flask import Markup
from flask_login import login_required, current_user

from . import account
from .. import db
from .forms import *
from ..util import *
from ..decorators import admin_required
from config import Config
from app.contracts import Contract
from ..models import Bank

from web3 import Web3
from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
from eth_utils import to_checksum_address

from logging import getLogger
logger = getLogger('api')

#+++++++++++++++++++++++++++++++
# Utils
#+++++++++++++++++++++++++++++++
def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')

#+++++++++++++++++++++++++++++++
# Views
#+++++++++++++++++++++++++++++++
@account.route('/list', methods=['GET'])
@login_required
@admin_required
def list():
    logger.info('list')
    users = User.query.all()
    return render_template('account/list.html', users=users)

@account.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    user = User.query.get_or_404(id)
    form = EditUserAdminForm(user=user)
    if request.method == 'POST':
        if form.validate():
            user.login_id = form.login_id.data
            user.user_name = form.user_name.data
            if 'icon' in request.files:
                upload_file = request.files["icon"]
                image_data = upload_file.read()
                if len(image_data) > 0:
                    user.icon = image_data
            iconclear = request.form.get('iconclear')
            if iconclear:
                user.icon = None
            user.role = Role.query.get(form.role.data)
            db.session.add(user)
            flash('%s さんの情報を更新しました。' % (user.user_name), 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('account/edit_admin.html', form=form, user=user)
    else: # GET
        form.login_id.data = user.login_id
        form.user_name.data = user.user_name
        form.icon.data = user.icon
        form.role.data = user.role.id
        return render_template('account/edit_admin.html', form=form, user=user)

@account.route('/edit_current', methods=['GET', 'POST'])
@login_required
def edit_current():
    form = EditUserForm(user=current_user)
    if request.method == 'POST':
        if form.validate():
            user = User.query.get(current_user.id)
            user.login_id = form.login_id.data
            user.user_name = form.user_name.data
            if 'icon' in request.files:
                upload_file = request.files["icon"]
                image_data = upload_file.read()
                if len(image_data) > 0:
                    user.icon = image_data
            iconclear = request.form.get('iconclear')
            if iconclear:
                user.icon = None
            db.session.add(user)
            flash('%s さんの情報を更新しました。' % (user.user_name), 'success')
            return redirect(request.args.get('next'))
        else:
            flash_errors(form)
            return render_template('account/edit.html', form=form, user=current_user, next_url=request.args.get('next'))
    else: # GET
        form.login_id.data = current_user.login_id
        form.user_name.data = current_user.user_name
        form.icon.data = current_user.icon
        return render_template('account/edit.html', form=form, user=current_user, next_url=request.args.get('next'))

@account.route('/pwdchg', methods=['GET', 'POST'])
@login_required
def pwdchg():
    form = PasswordChangeForm(user=current_user)
    if form.validate_on_submit():
        current_user.password = form.password.data
        db.session.add(current_user)
        flash('%s さんのパスワードを変更しました。' % (current_user.user_name), 'success')
        return redirect(request.args.get('next') or url_for('index.index'))
    flash_errors(form)
    return render_template('account/pwdchg.html', form=form, user=current_user, next_url=request.args.get('next'))

@account.route('/pwdinit', methods=['POST'])
@login_required
@admin_required
def pwdinit():
    u_id = request.form.get('id')
    user = User.query.get(int(u_id))
    token = secrets.token_urlsafe(6)
    user.password = token
    db.session.add(user)
    msg =  Markup('%s さんのパスワードを初期化しました。<h3>%s</h3>' % (user.user_name, token))
    flash(msg, 'confirm')
    return redirect(url_for('.edit', id=u_id))

@account.route('/regist', methods=['GET', 'POST'])
@login_required
@admin_required
def regist():
    form = RegistUserForm()
    if request.method == 'POST':
        if form.validate():
            user = User()
            user.login_id = form.login_id.data
            user.user_name = form.user_name.data
            if 'icon' in request.files:
                upload_file = request.files["icon"]
                image_data = upload_file.read()
                if len(image_data) > 0:
                    user.icon = image_data
            user.role = Role.query.get(form.role.data)
            db.session.add(user)
            flash('%s さんの情報を追加しました。' % (user.user_name), 'success')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('account/regist.html', form=form)
    else: # GET
        return render_template('account/regist.html', form=form)

@account.route('/delete', methods=['POST'])
@login_required
@admin_required
def delete():
    login_id = request.form.get('login_id')
    user = User.query.filter_by(login_id=login_id).first()
    db.session.delete(user)
    flash('%s さんの情報を削除しました。' % (user.user_name), 'success')
    return redirect(url_for('.list'))

#################################################
# 銀行口座情報の登録
#################################################
@account.route('/bankinfo', methods=['GET', 'POST'])
@login_required
@admin_required
def bankinfo():
    logger.info('account/bankinfo')
    form = BankInfoForm()
    if request.method == 'POST':
        if form.validate():
            eth_unlock_account()
            # PersonalInfoコントラクトに情報登録
            personalinfo_regist(form)
            # PaymentGatewayコントラクトに情報登録
            payment_account_regist(form)
            # DB に銀行口座情報登録
            bank_account_regist(form)

            flash('登録処理を受付ました。登録完了まで数分かかることがあります。', 'success')
            return render_template('account/bankinfo.html', form=form)
        else:
            flash_errors(form)
            return render_template('account/bankinfo.html', form=form)
    else: # GET
        form.name.data = ''
        form.bank_name.data = ''
        form.bank_code.data = ''
        form.branch_name.data = ''
        form.branch_code.data = ''
        form.account_type.data = ''
        form.account_number.data = ''
        form.account_holder.data = ''

        PersonalInfoContract = Contract.get_contract(
            'PersonalInfo',
            to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
        )

        # PersonalInfoコントラクトへの登録状態を取得
        bank = db.session.query(Bank).filter(Bank.eth_account == Config.ETH_ACCOUNT).first()

        if bank is not None:
            # 登録済みの場合は登録されている情報を取得
            
            try:
                # 銀行口座情報の取得
                form.name.data = bank.name
                form.bank_name.data = bank.bank_name
                form.bank_code.data = bank.bank_code
                form.branch_name.data = bank.branch_name
                form.branch_code.data = bank.branch_code
                form.account_type.data = bank.account_type
                form.account_number.data = bank.account_number
                form.account_holder.data = bank.account_holder
            except:
                pass

        return render_template('account/bankinfo.html', form=form, bank=bank)

def personalinfo_regist(form):
    # ローカルに保存されている発行体のRSA公開鍵を取得
    key = RSA.importKey(open('data/rsa/public.pem').read())
    cipher = PKCS1_OAEP.new(key)

    personal_info_json = {
        "name": form.name.data,
        "address":{
            "postal_code":"",
            "prefecture":"",
            "city":"",
            "address1":"",
            "address2":""
        },
        "email":""
    }

    # 銀行口座情報の暗号化
    personal_info_ciphertext = \
        base64.encodestring(
            cipher.encrypt(json.dumps(personal_info_json).encode('utf-8')))

    # PersonalInfo登録
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo',
        to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    )
    p_gas = PersonalInfoContract.estimateGas().\
        register(Config.ETH_ACCOUNT, personal_info_ciphertext)
    p_txid = PersonalInfoContract.functions.\
        register(Config.ETH_ACCOUNT, personal_info_ciphertext).\
        transact({'from':Config.ETH_ACCOUNT, 'gas':p_gas})

def payment_account_regist(form):
    # 収納代行業者のアドレス
    agent_address = to_checksum_address(Config.AGENT_ADDRESS)

    # 収納代行業者のRSA公開鍵を取得
    if Config.APP_ENV == 'production':
        company_list = []
        isExist = False
        try:
            company_list = requests.get(Config.PAYMENT_AGENT_LIST_URL).json()
        except:
            pass
        for company_info in company_list:
            if to_checksum_address(company_info['address']) == agent_address:
                isExist = True
                key_bank = RSA.importKey(company_info['rsa_publickey'].replace('\\n',''))
        if isExist == False:
            flash('決済代行業者の情報を取得できません。決済代行業者のアドレスが正しいか確認してください。', 'error')
            return render_template('account/bankinfo.html', form=form)
    else:
        # ローカルのRSA公開鍵を取得
        # NOTE: 収納代行業者のものではなく、発行体自身の公開鍵である
        key_bank = RSA.importKey(open('data/rsa/public.pem').read())

    cipher = PKCS1_OAEP.new(key_bank)

    payment_account_json = {
        "name": form.name.data,
        "bank_account":{
            "bank_name": form.bank_name.data,
            "bank_code": form.bank_code.data,
            "branch_office": form.branch_name.data,
            "branch_code": form.branch_code.data,
            "account_type": int(form.account_type.data),
            "account_number": form.account_number.data,
            "account_holder": form.account_holder.data
        }
    }
    payment_account_message_string = json.dumps(payment_account_json)

    # 銀行口座情報の暗号化
    payment_account_ciphertext = \
        base64.encodestring(
            cipher.encrypt(payment_account_message_string.encode('utf-8')))

    # WhiteList登録
    payment_gateway_address = to_checksum_address(Config.PAYMENT_GATEWAY_CONTRACT_ADDRESS)
    PaymentGatewayContract = Contract.get_contract('PaymentGateway', payment_gateway_address)
    w_gas = PaymentGatewayContract.estimateGas().\
        register(agent_address, payment_account_ciphertext)
    w_txid = PaymentGatewayContract.functions.\
        register(agent_address, payment_account_ciphertext).\
        transact({'from':Config.ETH_ACCOUNT, 'gas':w_gas})

def bank_account_regist(form):
    # 入力内容を格納
    bank_account = Bank()
    bank_account.eth_account = Config.ETH_ACCOUNT
    bank_account.name = form.name.data
    bank_account.bank_name = form.bank_name.data
    bank_account.bank_code = form.bank_code.data
    bank_account.branch_name = form.branch_name.data
    bank_account.branch_code = form.branch_code.data
    bank_account.account_type = form.account_type.data
    bank_account.account_number = form.account_number.data
    bank_account.account_holder = form.account_holder.data

    bank = db.session.query(Bank).filter(Bank.eth_account == Config.ETH_ACCOUNT).first()

    # 入力された口座情報をDBに登録
    if bank is None:
        db.session.add(bank_account)
    # 既に登録されている場合、更新
    else :
        bank.name = bank_account.name
        bank.bank_name = bank_account.bank_name
        bank.bank_code = bank_account.bank_code
        bank.branch_name = bank_account.branch_name
        bank.branch_code = bank_account.branch_code
        bank.account_type = bank_account.account_type
        bank.account_number = bank_account.account_number
        bank.account_holder = bank_account.account_holder
    db.session.commit()
        

#+++++++++++++++++++++++++++++++
# Custom Filter
#+++++++++++++++++++++++++++++++
@account.app_template_filter()
def format_date(date): # date = datetime object.
    if date:
        if isinstance(date, datetime.datetime):
            return date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(date, datetime.date):
            return date.strftime('%Y/%m/%d')
    return ''

@account.app_template_filter()
def img_convert(icon):
    if icon:
        img = b64encode(icon)
        return img.decode('utf8')
    return None
