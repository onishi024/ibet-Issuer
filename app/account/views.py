# -*- coding:utf-8 -*-
import secrets
import datetime
import json
import base64
from flask import Flask, request, redirect, url_for, flash, session
from flask_restful import Resource, Api
from flask import render_template
from flask import jsonify, abort
from flask_login import login_required, current_user
from flask import Markup, jsonify
from ..decorators import admin_required
from config import Config

from sqlalchemy import desc

from . import account
from .. import db
from ..models import Role, User, BankInfo
from .forms import *
from flask import current_app
from cryptography.fernet import Fernet

from logging import getLogger
logger = getLogger('api')

from web3 import Web3
from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
from eth_utils import to_checksum_address

from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

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

@account.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')

#################################################
# 企業情報登録
#################################################
@account.route('/bankinfo', methods=['GET', 'POST'])
@login_required
@admin_required
def bankinfo():
    logger.info('account/bankinfo')
    bank_infos = BankInfo.query.all()
    if len(bank_infos) == 1:
        bank_info = bank_infos[0]
    else:
        bank_info = None
    form = BankInfoForm(bank_info=bank_info)
    if request.method == 'POST':
        if form.validate():
            if bank_info is None:
                bank_info = BankInfo()
            # DB登録
            bank_info.name = form.name.data
            bank_info.bank_name = form.bank_name.data
            bank_info.bank_code = form.bank_code.data
            bank_info.branch_name = form.branch_name.data
            bank_info.branch_code = form.branch_code.data
            bank_info.account_type = form.account_type.data
            bank_info.account_number = form.account_number.data
            bank_info.account_holder = form.account_holder.data
            db.session.add(bank_info)

            # unlock
            web3.personal.unlockAccount(Config.ETH_ACCOUNT, Config.ETH_ACCOUNT_PASSWORD, 1000)

            # public key
            key = RSA.importKey(open('data/rsa/public.pem').read())
            cipher = PKCS1_OAEP.new(key)

            # personInfo暗号文字列
            personal_info_json = {
                "name": bank_info.name,
                "address":{
                    "postal_code":"",
                    "prefecture":"",
                    "city":"",
                    "address1":"",
                    "address2":""
                },
                "bank_account":{
                    "bank_name": bank_info.bank_name,
                    "bank_code": bank_info.bank_code,
                    "branch_office": bank_info.branch_name,
                    "branch_code": bank_info.branch_code,
                    "account_type": bank_info.account_type,
                    "account_number": bank_info.account_number,
                    "account_holder": bank_info.account_holder
                }
            }
            personal_info_message_string = json.dumps(personal_info_json)
            personal_info_ciphertext = base64.encodestring(cipher.encrypt(personal_info_message_string.encode('utf-8')))
            
            # personInfo register
            personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
            personalinfo_abi = Config.PERSONAL_INFO_CONTRACT_ABI
            PersonalInfoContract = web3.eth.contract(
                address = personalinfo_address,
                abi = personalinfo_abi
            )
            p_gas = PersonalInfoContract.estimateGas().register(Config.ETH_ACCOUNT, personal_info_ciphertext)
            p_txid = PersonalInfoContract.functions.register(Config.ETH_ACCOUNT, personal_info_ciphertext).\
                transact({'from':Config.ETH_ACCOUNT, 'gas':p_gas})

            # WhiteList Contract
            whitelist_address = to_checksum_address(Config.WHITE_LIST_CONTRACT_ADDRESS)
            whitelist_abi = Config.WHITE_LIST_CONTRACT_ABI
            WhiteListContract = web3.eth.contract(
                address = whitelist_address,
                abi = whitelist_abi
            )



            flash('登録完了しました。', 'success')
            return render_template('account/bankinfo.html', form=form)
        else:
            flash_errors(form)
            return render_template('account/bankinfo.html', form=form)
    else: # GET
        if bank_info is not None:
            form.name.data = bank_info.name
            form.bank_name.data = bank_info.bank_name
            form.bank_code.data = bank_info.bank_code
            form.branch_name.data = bank_info.branch_name
            form.branch_code.data = bank_info.branch_code
            form.account_type.data = bank_info.account_type
            form.account_number.data = bank_info.account_number
            form.account_holder.data = bank_info.account_holder
        return render_template('account/bankinfo.html', form=form)

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
