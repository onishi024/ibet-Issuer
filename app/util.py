import base64
import json
from base64 import b64encode
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=+9), 'JST')

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from .models import Token
from config import Config
from app.contracts import Contract

from web3 import Web3
from eth_utils import to_checksum_address
from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


###
# 債券トークンの保有者一覧、token_nameを返す
###
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
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # Straight-Bond Exchange Contract
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    ExchangeContract = Contract.get_contract(
        'IbetStraightBondExchange', token_exchange_address)

    # PersonalInfo Contract
    personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personalinfo_address)

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

###
# クーポントークンの保有者一覧、token_nameを返す
###
def get_holders_coupon(token_address):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    # Coupon Token Contract
    # Note: token_addressに対して、Couponトークンのものであるかはチェックしていない。
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # PersonalInfo Contract
    personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personalinfo_address)

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

    # 残高（balance）、または使用済（used）が存在する情報を抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        used = TokenContract.functions.usedOf(account_address).call()
        if balance > 0 or used > 0:
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
                'used': used
            }
            holders.append(holder)

    return holders, token_name

###
# トークン保有者のPersonalInfoを返す
###
def get_holder(token_address, account_address):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        pass

    # Token Contract
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # PersonalInfo Contract
    personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    PersonalInfoContract = Contract.get_contract(
        'PersonalInfo', personalinfo_address)

    personal_info = {
        "name":"--",
        "address":{
            "postal_code":"--",
            "prefecture":"--",
            "city":"--",
            "address1":"--",
            "address2":"--"
        },
        "bank_account":{
            "bank_name": "--",
            "branch_office": "--",
            "account_type": "--",
            "account_number": "--",
            "account_holder": "--"
        }
    }

    token_owner = TokenContract.functions.owner().call()

    encrypted_info = PersonalInfoContract.functions.\
        personal_info(account_address, token_owner).call()[2]

    if encrypted_info == '' or cipher == None:
        pass
    else:
        ciphertext = base64.decodestring(encrypted_info.encode('utf-8'))
        try:
            message = cipher.decrypt(ciphertext)
            personal_info = json.loads(message)
        except:
            pass
    return personal_info

###
# クーポントークンの利用履歴を返す
###
def get_usege_history_coupon(token_address):
    # Coupon Token Contract
    # Note: token_addressに対して、Couponトークンのものであるかはチェックしていない。
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').\
        replace('True', 'true').replace('False', 'false'))
    CouponContract = web3.eth.contract(
        address= token_address, abi = token_abi)

    # クーポン名を取得
    token_name = CouponContract.functions.name().call()

    # クーポントークンの消費イベント（Consume）を検索
    try:
        event_filter = CouponContract.eventFilter(
            'Consume', {
                'filter':{},
                'fromBlock':'earliest'
            }
        )
        entries = event_filter.get_all_entries()
        web3.eth.uninstallFilter(event_filter.filter_id)
    except:
        entries = []

    usage_list = []
    for entry in entries:
        usage = {
            'block_timestamp': datetime.fromtimestamp(
                web3.eth.getBlock(entry['blockNumber'])['timestamp'],JST).\
                strftime("%Y/%m/%d %H:%M:%S"),
            'consumer': entry['args']['consumer'],
            'value': entry['args']['value']
        }
        usage_list.append(usage)

    return token_address, token_name, usage_list
