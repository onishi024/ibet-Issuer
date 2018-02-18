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
from .forms import IssueTokenForm, TokenSettingForm
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
            name = '<処理中...>'
            symbol = '<処理中...>'
        token_list.append({
            'name':name,
            'symbol':symbol,
            'created':row.created,
            'tx_hash':row.tx_hash,
            'token_address':row.token_address
        })

    return render_template('token/list.html', tokens=token_list)


@token.route('/setting/<string:token_address>', methods=['GET', 'POST'])
@login_required
def setting(token_address):
    logger.info('token.token_address')
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token.token_address,
        abi = token_abi,
        bytecode = token.bytecode,
        bytecode_runtime = token.bytecode_runtime
    )

    name = TokenContract.functions.name().call()
    total_supply = TokenContract.functions.totalSupply().call()
    symbol = TokenContract.functions.symbol().call()
    decimals = TokenContract.functions.decimals().call()

    form = TokenSettingForm()
    if request.method == 'POST':
        pass
    else: # GET
        form.token_address.data = token.token_address
        form.token_name.data = name
        form.total_supply.data = total_supply
        form.token_symbol.data = symbol
        form.token_decimals.data = decimals
        form.image_small.data = None
        form.image_medium.data = None
        form.image_large.data = None
        form.abi.data = token.abi
        form.bytecode.data = token.bytecode
        return render_template('token/setting.html', form=form)


@token.route('/release', methods=['POST'])
@login_required
def release():
    token_address = request.form.get('token_address')

    list_contract_address = '0xf644A58d77D78f797F0511349c41489f96478Ce0'

    list_contract_abi = json.loads('[{"constant": true,"inputs": [{"name": "_num","type": "uint256"}],"name": "getToken","outputs": [{"name": "token_address","type": "address"},{"name": "owner_address","type": "address"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": true,"inputs": [{"name": "_token_address","type": "address"}],"name": "getOwnerAddress","outputs": [{"name": "issuer_address","type": "address"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": true,"inputs": [],"name": "getListLength","outputs": [{"name": "length","type": "uint256"}],"payable": false,"stateMutability": "view","type": "function"},{"constant": false,"inputs": [{"name": "_token_address","type": "address"},{"name": "_new_owner_address","type": "address"}],"name": "changeOwner","outputs": [],"payable": false,"stateMutability": "nonpayable","type": "function"},{"constant": false,"inputs": [{"name": "_token_address","type": "address"}],"name": "register","outputs": [],"payable": false,"stateMutability": "nonpayable","type": "function"}]')

    list_contract_bytecode = '6060604052341561000f57600080fd5b6108998061001e6000396000f30060606040526004361061006d576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff1680634420e4861461007257806391657049146100ab578063b65c531b14610124578063e4b50cb81461014d578063f00d4b5d146101e3575b600080fd5b341561007d57600080fd5b6100a9600480803573ffffffffffffffffffffffffffffffffffffffff1690602001909190505061023b565b005b34156100b657600080fd5b6100e2600480803573ffffffffffffffffffffffffffffffffffffffff16906020019091905050610439565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b341561012f57600080fd5b6101376104a1565b6040518082815260200191505060405180910390f35b341561015857600080fd5b61016e60048080359060200190919050506104ae565b604051808373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019250505060405180910390f35b34156101ee57600080fd5b610239600480803573ffffffffffffffffffffffffffffffffffffffff1690602001909190803573ffffffffffffffffffffffffffffffffffffffff1690602001909190505061053c565b005b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff161415156102be57600080fd5b336000808373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055506001805480600101828161034f91906107ce565b9160005260206000209060020201600060408051908101604052808573ffffffffffffffffffffffffffffffffffffffff1681526020013373ffffffffffffffffffffffffffffffffffffffff16815250909190915060008201518160000160006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555060208201518160010160006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050505050565b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050919050565b6000600180549050905090565b6000806001838154811015156104c057fe5b906000526020600020906002020160000160009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16915060018381548110151561050357fe5b906000526020600020906002020160010160009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050915091565b6000806000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16141515156105c157600080fd5b3373ffffffffffffffffffffffffffffffffffffffff166000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614151561065957600080fd5b816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550600090505b6001805490508110156107c9578273ffffffffffffffffffffffffffffffffffffffff1660018281548110151561070e57fe5b906000526020600020906002020160000160009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156107bc578160018281548110151561076c57fe5b906000526020600020906002020160010160006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055505b80806001019150506106db565b505050565b8154818355818115116107fb576002028160020283600052602060002091820191016107fa9190610800565b5b505050565b61086a91905b8082111561086657600080820160006101000a81549073ffffffffffffffffffffffffffffffffffffffff02191690556001820160006101000a81549073ffffffffffffffffffffffffffffffffffffffff021916905550600201610806565b5090565b905600a165627a7a72305820dc2cd4cfc66c84310653d2da0505d26c0861b4035b5badc59412604b8647e3f20029'

    list_contract_bytecode_runtime = '60606040526004361061006d576000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff1680634420e4861461007257806391657049146100ab578063b65c531b14610124578063e4b50cb81461014d578063f00d4b5d146101e3575b600080fd5b341561007d57600080fd5b6100a9600480803573ffffffffffffffffffffffffffffffffffffffff1690602001909190505061023b565b005b34156100b657600080fd5b6100e2600480803573ffffffffffffffffffffffffffffffffffffffff16906020019091905050610439565b604051808273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200191505060405180910390f35b341561012f57600080fd5b6101376104a1565b6040518082815260200191505060405180910390f35b341561015857600080fd5b61016e60048080359060200190919050506104ae565b604051808373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020018273ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1681526020019250505060405180910390f35b34156101ee57600080fd5b610239600480803573ffffffffffffffffffffffffffffffffffffffff1690602001909190803573ffffffffffffffffffffffffffffffffffffffff1690602001909190505061053c565b005b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff161415156102be57600080fd5b336000808373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055506001805480600101828161034f91906107ce565b9160005260206000209060020201600060408051908101604052808573ffffffffffffffffffffffffffffffffffffffff1681526020013373ffffffffffffffffffffffffffffffffffffffff16815250909190915060008201518160000160006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555060208201518160010160006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555050505050565b60008060008373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050919050565b6000600180549050905090565b6000806001838154811015156104c057fe5b906000526020600020906002020160000160009054906101000a900473ffffffffffffffffffffffffffffffffffffffff16915060018381548110151561050357fe5b906000526020600020906002020160010160009054906101000a900473ffffffffffffffffffffffffffffffffffffffff169050915091565b6000806000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16141515156105c157600080fd5b3373ffffffffffffffffffffffffffffffffffffffff166000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614151561065957600080fd5b816000808573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550600090505b6001805490508110156107c9578273ffffffffffffffffffffffffffffffffffffffff1660018281548110151561070e57fe5b906000526020600020906002020160000160009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1614156107bc578160018281548110151561076c57fe5b906000526020600020906002020160010160006101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff1602179055505b80806001019150506106db565b505050565b8154818355818115116107fb576002028160020283600052602060002091820191016107fa9190610800565b5b505050565b61086a91905b8082111561086657600080820160006101000a81549073ffffffffffffffffffffffffffffffffffffffff02191690556001820160006101000a81549073ffffffffffffffffffffffffffffffffffffffff021916905550600201610806565b5090565b905600a165627a7a72305820dc2cd4cfc66c84310653d2da0505d26c0861b4035b5badc59412604b8647e3f20029'

    web3.personal.unlockAccount(web3.eth.accounts[0],"password",1000)

    ListContract = web3.eth.contract(
        address = list_contract_address,
        abi = list_contract_abi,
        bytecode = list_contract_bytecode,
        bytecode_runtime = list_contract_bytecode_runtime,
    )

    register_txid = ListContract.functions.register(token_address).transact(
        {'from':web3.eth.accounts[0], 'gas':3000000}
    )

    flash('公開中です。公開開始までに数分程かかることがあります。', 'success')
    return redirect(url_for('.setting', token_address=token_address))


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
