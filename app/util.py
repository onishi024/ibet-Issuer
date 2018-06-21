import base64
import json
from base64 import b64encode

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from .models import Token
from config import Config

from web3 import Web3
from eth_utils import to_checksum_address
from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


###
# トークン保有者一覧、token_nameを返す
###
def get_holders(token_address, template_id):
    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        traceback.print_exc()
        pass

    # Token Contract
    token = Token.query.filter(Token.token_address==token_address).first()
    token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

    TokenContract = web3.eth.contract(
        address= token_address,
        abi = token_abi
    )

    # Exchange Contract
    token_exchange_address = to_checksum_address(Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS)
    token_exchange_abi = Config.IBET_SB_EXCHANGE_CONTRACT_ABI
    ExchangeContract = web3.eth.contract(
        address = token_exchange_address,
        abi = token_exchange_abi
    )

    # PersonalInfo Contract
    personalinfo_address = to_checksum_address(Config.PERSONAL_INFO_CONTRACT_ADDRESS)
    personalinfo_abi = Config.PERSONAL_INFO_CONTRACT_ABI
    PersonalInfoContract = web3.eth.contract(
        address = personalinfo_address,
        abi = personalinfo_abi
    )

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
        # 債券の場合は、注文中の残高（commitment）を抽出
        commitment = 0
        if template_id == Config.TEMPLATE_ID_SB:
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
                'commitment':commitment,
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
    personalinfo_abi = Config.PERSONAL_INFO_CONTRACT_ABI
    PersonalInfoContract = web3.eth.contract(
        address = personalinfo_address,
        abi = personalinfo_abi
    )

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