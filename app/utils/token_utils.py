import base64
import json
from flask import abort
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from app.models import Token
from app.utils import ContractUtils
from config import Config
from logging import getLogger

logger = getLogger('api')

from web3 import Web3
from eth_utils import to_checksum_address
from web3.middleware import geth_poa_middleware

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


class TokenUtils:

    @staticmethod
    def get_contract(token_address: str):
        """
        トークンコントラクト取得

        :param token_address: トークンアドレス
        :return: コントラクト
        """
        token = Token.query.filter(Token.token_address == token_address).first()
        if token is None:
            abort(404)
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        return web3.eth.contract(address=token.token_address, abi=token_abi)

    @staticmethod
    def get_holder(token_address: str, account_address: str, custom_personal_info_address=None, default_value='--'):
        """
        トークン保有者の個人情報取得

        :param token_address: トークンのアドレス
        :param account_address: トークン保有者のアドレス
        :param custom_personal_info_address: 個人情報を格納している個人情報コントラクトのアドレス。
            未指定の場合はシステムデフォルトの個人情報コントラクトアドレスを使用する。
        :param default_value: 値が未設定の項目に設定する初期値。(未指定時: '--')
        :return: 個人情報（PersonalInfo）
        """
        if not Web3.isAddress(account_address):
            abort(404)

        # RSA秘密鍵の取得
        cipher = None
        try:
            key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
            cipher = PKCS1_OAEP.new(key)
        except Exception as e:
            logger.error(e)
            pass

        # トークン発行体アドレス取得
        token = Token.query.filter(Token.token_address == token_address).first()
        if token is None:
            abort(404)
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        TokenContract = web3.eth.contract(address=token_address, abi=token_abi)
        token_owner = TokenContract.functions.owner().call()

        # PersonalInfo Contract 接続
        if custom_personal_info_address is None:
            personalinfo_address = Config.PERSONAL_INFO_CONTRACT_ADDRESS
        else:
            personalinfo_address = to_checksum_address(custom_personal_info_address)
        PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', personalinfo_address)

        # デフォルト値
        personal_info = {
            "name": default_value,
            "address": {
                "postal_code": default_value,
                "prefecture": default_value,
                "city": default_value,
                "address1": default_value,
                "address2": default_value
            },
            "email": default_value,
            "birth": default_value
        }

        # 個人情報取得
        encrypted_info = PersonalInfoContract.functions.personal_info(account_address, token_owner).call()[2]
        if encrypted_info == '' or cipher is None:
            pass
        else:
            try:
                ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                message = cipher.decrypt(ciphertext)  # 復号化
                personal_info = TokenUtils.validateDictStruct(personal_info, json.loads(message))
            except Exception as e:
                logger.warning(e)
                pass
        return personal_info

    @staticmethod
    def validateDictStruct(madict, trdict):
        """
        第1引数の辞書の構造を正として、第2引数の辞書のプロパティとバリューの存在有無をチェックする
        :param madict: 正となる辞書
        :param trdict: チェック対象の辞書
        :return:
        """
        resdict = {}
        if not isinstance(madict, dict) or not isinstance(trdict, dict):
            return resdict
        for key in madict:
            if key in trdict and isinstance(madict[key], dict) and isinstance(trdict[key], dict):
                resdict[key] = TokenUtils.validateDictStruct(madict[key], trdict[key])
            elif key not in trdict or trdict[key] == "" or (
                    isinstance(madict[key], dict) and not isinstance(trdict[key], dict)) or (
                    not isinstance(madict[key], dict) and isinstance(trdict[key], dict)):
                resdict[key] = madict[key]
            elif not isinstance(madict[key], dict):
                resdict[key] = trdict[key]
        return resdict
