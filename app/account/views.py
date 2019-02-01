# -*- coding:utf-8 -*-
import secrets
import datetime
import json
import base64
import requests
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from flask import Flask, request, redirect, url_for, flash, session
from flask_restful import Resource, Api
from flask import render_template
from flask import jsonify, abort
from flask_login import login_required, current_user
from flask import Markup, jsonify
from flask import current_app
from sqlalchemy import desc

from . import account
from .. import db
from ..models import Role, User
from .forms import *
from ..util import *
from ..decorators import admin_required
from config import Config
from app.contracts import Contract

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
            # WhiteListコントラクトに情報登録
            whitelist_regist(form)

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
        isRegistered = PersonalInfoContract.functions.\
            isRegistered(Config.ETH_ACCOUNT, Config.ETH_ACCOUNT).call()

        if isRegistered:
            # 登録済みの場合は登録されている情報を取得
            personal_info = PersonalInfoContract.functions.\
                personal_info(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT).call()
            try:
                # 銀行口座情報の復号化
                key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
                cipher = PKCS1_OAEP.new(key)
                ciphertext = base64.decodestring(personal_info[2].encode('utf-8'))
                message = cipher.decrypt(ciphertext)
                personalinfo_json = json.loads(message)
                form.name.data = personalinfo_json['name']
                form.bank_name.data = personalinfo_json['bank_account']['bank_name']
                form.bank_code.data = personalinfo_json['bank_account']['bank_code']
                form.branch_name.data = personalinfo_json['bank_account']['branch_office']
                form.branch_code.data = personalinfo_json['bank_account']['branch_code']
                form.account_type.data = str(personalinfo_json['bank_account']['account_type'])
                form.account_number.data = personalinfo_json['bank_account']['account_number']
                form.account_holder.data = personalinfo_json['bank_account']['account_holder']
            except:
                pass

        return render_template('account/bankinfo.html', form=form)

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
        "email":"",
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

def whitelist_regist(form):
    # 収納代行業社のアドレス
    agent_address = to_checksum_address(Config.AGENT_ADDRESS)

    # 収納代行業社のRSA公開鍵を取得
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
        # ローカルのRSA公開鍵（発行体自身の公開鍵）を取得
        key_bank = RSA.importKey(open('data/rsa/public.pem').read())

    cipher = PKCS1_OAEP.new(key_bank)

    whitelist_json = {
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
    whitelist_message_string = json.dumps(whitelist_json)

    # 銀行口座情報の暗号化
    whitelist_ciphertext = \
        base64.encodestring(
            cipher.encrypt(whitelist_message_string.encode('utf-8')))

    # WhiteList登録
    whitelist_address = to_checksum_address(Config.WHITE_LIST_CONTRACT_ADDRESS)
    WhiteListContract = Contract.get_contract('WhiteList', whitelist_address)
    w_gas = WhiteListContract.estimateGas().\
        register(agent_address, whitelist_ciphertext)
    w_txid = WhiteListContract.functions.\
        register(agent_address, whitelist_ciphertext).\
        transact({'from':Config.ETH_ACCOUNT, 'gas':w_gas})

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
