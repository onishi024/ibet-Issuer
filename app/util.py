import base64
import json
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=+9), 'JST')

from flask import abort

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

####################################################
# EOAのアカウントロック解除
####################################################
def eth_unlock_account():
    web3.personal.unlockAccount(Config.ETH_ACCOUNT,Config.ETH_ACCOUNT_PASSWORD,60)

####################################################
# トークン保有者のPersonalInfoを返す
####################################################
def get_holder(token_address, account_address):
    if not Web3.isAddress(account_address):
        abort(404)

    cipher = None
    try:
        key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
        cipher = PKCS1_OAEP.new(key)
    except:
        pass

    # Token Contract
    token = Token.query.filter(Token.token_address==token_address).first()
    if token is None:
        abort(404)

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
        "email":"--"
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
            personal_info = validateDictStruct(personal_info, json.loads(message))
        except:
            pass
    return personal_info

####################################################
# 第1引数の辞書の構造を正として、第2引数の辞書のプロパティとバリューの存在有無をチェックする。
####################################################
def validateDictStruct(madict, trdict):
    resdict = {}
    if not isinstance(madict, dict) or not isinstance(trdict, dict):
        return resdict
    for key in madict:
        if key in trdict and isinstance(madict[key], dict) and isinstance(trdict[key], dict):
            resdict[key] = validateDictStruct(madict[key], trdict[key])
        elif key not in trdict or trdict[key] == "" or (isinstance(madict[key], dict) and not isinstance(trdict[key], dict)) or (not isinstance(madict[key], dict) and isinstance(trdict[key], dict)):
            resdict[key] = madict[key]
        elif not isinstance(madict[key], dict):
            resdict[key] = trdict[key]
    return resdict