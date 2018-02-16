# -*- coding:utf-8 -*-
import secrets
import datetime
import json
from base64 import b64encode
from flask import Flask, request, redirect, url_for, flash, session
from flask_restful import Resource, Api
from flask import render_template
from flask import jsonify, abort
from flask_login import login_required, current_user
from flask import Markup, jsonify
from flask import current_app

from web3 import Web3
from solc import compile_source
from sqlalchemy import desc

from . import token
from .. import db
from ..models import Role, User, Token
from .forms import IssueTokenForm
from ..decorators import admin_required
from config import Config

from logging import getLogger
logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))

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
@token.route('/tokenlist', methods=['GET'])
@login_required
def list():
    logger.info('list')
    tokens = Token.query.all()
    token_list = []
    for row in tokens:
        if row.token_address != None:
            MyContract = web3.eth.contract(
                address=row.token_address,
                abi = json.loads(
                    row.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')),
                bytecode = row.bytecode,
                bytecode_runtime = row.bytecode_runtime
            )
            name = MyContract.functions.name().call()
            symbol = MyContract.functions.symbol().call()
        else:
            name = '<NotConfirmed>'
            symbol = '<NotConfirmed>'
        token_list.append({
            'name':name,
            'symbol':symbol,
            'created':row.created,
            'tx_hash':row.tx_hash
        })

    return render_template('token/list.html', tokens=token_list)

@token.route('/issue', methods=['GET', 'POST'])
@login_required
def issue():
    logger.info('issue')
    form = IssueTokenForm()
    if request.method == 'POST':
        if form.validate():

            source_code = 'contract MyToken {  string public name;  string public symbol;  uint8 public decimals;  uint256 public totalSupply;  mapping (address => uint256) public balanceOf;  event Transfer(address indexed from, address indexed to, uint256 value);  event Issue(address indexed sender, uint256 value);  function MyToken(uint256 _supply, string _name, string _symbol, uint8 _decimals) public {    balanceOf[msg.sender] = _supply;    name = _name;    symbol = _symbol;    decimals = _decimals;    totalSupply = _supply;    Issue(msg.sender, _supply);  }  function transfer(address _to, uint256 _value) public {    require(balanceOf[msg.sender] > _value) ;    require(balanceOf[_to] + _value > balanceOf[_to]) ;    balanceOf[msg.sender] -= _value;    balanceOf[_to] += _value;    Transfer(msg.sender, _to, _value);  }  function getBalanceOf(address _owner) public constant returns (uint256){      return balanceOf[_owner];  }}'

            web3.personal.unlockAccount(web3.eth.accounts[0],"password",1000)

            compile_sol = compile_source(source_code)

            MyContract = web3.eth.contract(
                abi = compile_sol['<stdin>:MyToken']['abi'],
                bytecode = compile_sol['<stdin>:MyToken']['bin'],
                bytecode_runtime = compile_sol['<stdin>:MyToken']['bin-runtime'],
            )

            arguments = [
                form.total_supply.data,
                form.token_name.data,
                form.token_symbol.data,
                form.token_decimals.data
            ]

            tx_hash = MyContract.deploy(
                transaction={'from':web3.eth.accounts[0], 'gas':3000000},
                args=arguments
            ).hex()

            token = Token()
            token.template_id = 1
            token.tx_hash = tx_hash
            token.admin_address = None
            token.token_address = None
            token.abi = str(compile_sol['<stdin>:MyToken']['abi'])
            token.bytecode = compile_sol['<stdin>:MyToken']['bin']
            token.bytecode_runtime = compile_sol['<stdin>:MyToken']['bin-runtime']
            db.session.add(token)

            msg = Markup('新規発行を受け付けました。発行完了までに数分程かかることがあります。 受付ID：%s' % (tx_hash))
            flash(msg, 'confirm')
            return redirect(url_for('.list'))
        else:
            flash_errors(form)
            return render_template('token/issue.html', form=form)
    else: # GET
        return render_template('token/issue.html', form=form)


@token.route('/PermissionDenied', methods=['GET', 'POST'])
@login_required
def permissionDenied():
    return render_template('permissiondenied.html')

#+++++++++++++++++++++++++++++++
# Custom Filter
#+++++++++++++++++++++++++++++++
@token.app_template_filter()
def format_date(date): # date = datetime object.
    if date:
        if isinstance(date, datetime.datetime):
            return date.strftime('%Y/%m/%d %H:%M')
        elif isinstance(date, datetime.date):
            return date.strftime('%Y/%m/%d')
    return ''

@token.app_template_filter()
def img_convert(icon):
    if icon:
        img = b64encode(icon)
        return img.decode('utf8')
    return None
