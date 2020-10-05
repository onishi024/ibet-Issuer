import base64
import json
from typing import Optional

import requests
from flask import abort
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from app.models import Token, Issuer
from app.utils import ContractUtils
from app.exceptions import EthRuntimeError
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
    def get_contract(token_address: str, issuer_address: Optional[str], template_id: int = None):
        """
        トークンコントラクト取得

        :param token_address: トークンアドレス
        :param issuer_address: トークン発行体アドレス。ログインユーザごとに参照できるトークンを制限するために使用する。
            Indexer/processor等でログインユーザによる制限が不要な場合はNoneを指定する。
        :param template_id:
            （任意項目）　テンプレートID（例 :py:attr:`.Config.TEMPLATE_ID_SB` ）。
            トークンの種類を限定したいときに設定する。たとえば、債券専用の処理にクライアントが誤って
            会員権のトークンアドレスを送信し、そのまま間違った処理が実行されることを防ぎたい場合に設定する。
            テンプレートID指定するとトークンアドレスとテンプレートIDの組み合わせが正しくない場合にエラーとなる。
        :return: コントラクト
        :raises HTTPException:
            トークンアドレスが未登録の場合、
            トークンアドレスとテンプレートIDの組み合わせが正しくない場合（テンプレートID指定時のみ）、
            HTTPステータス404で例外を発生させる。
        """
        token_query = Token.query.filter(Token.token_address == token_address)
        if issuer_address is not None:
            # Tokenテーブルのadmin_addressはchecksumアドレスではないため小文字にして検索
            token_query = token_query.filter(Token.admin_address == issuer_address.lower())
        if template_id is not None:
            token_query = token_query.filter(Token.template_id == template_id)
        token = token_query.first()

        if token is None:
            abort(404)
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        return web3.eth.contract(address=token.token_address, abi=token_abi)

    @staticmethod
    def get_holder(account_address: str, issuer_address: str, custom_personal_info_address=None,
                   default_value='--'):
        """
        トークン保有者の個人情報取得

        :param account_address: トークン保有者のアドレス
        :param issuer_address: 個人情報を取得する発行体アドレス
        :param custom_personal_info_address: 個人情報を格納している個人情報コントラクトのアドレス。
            未指定の場合はシステムデフォルトの個人情報コントラクトアドレスを使用する。
        :param default_value: 値が未設定の項目に設定する初期値。(未指定時: '--')
        :return: 個人情報（PersonalInfo）
        """
        issuer = Issuer.query.filter(Issuer.eth_account == issuer_address).first()

        # RSA秘密鍵の取得
        cipher = None
        try:
            key = RSA.importKey(issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
            cipher = PKCS1_OAEP.new(key)
        except Exception as e:
            logger.error(e)
            pass

        # PersonalInfo Contract 接続
        if custom_personal_info_address is None:
            personalinfo_address = issuer.personal_info_contract_address
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
        encrypted_info = PersonalInfoContract.functions.personal_info(account_address, issuer.eth_account).call()[2]
        if encrypted_info == '' or cipher is None:
            pass
        else:
            try:
                ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                # NOTE:
                # JavaScriptでRSA暗号化する際に、先頭が0x00の場合は00を削った状態でデータが連携される。
                # そのままdecryptすると、ValueError（Ciphertext with incorrect length）になるため、
                # 先頭に再度00を加えて、decryptを行う。
                if len(ciphertext) == 1279:
                    hex_fixed = "00" + ciphertext.hex()
                    ciphertext = base64.b16decode(hex_fixed.upper())
                message = cipher.decrypt(ciphertext)  # 復号化
                personal_info = TokenUtils.validateDictStruct(personal_info, json.loads(message))
            except Exception as err:
                logger.error(f"Failed to decrypt: {err}")
        return personal_info

    @staticmethod
    def modify_personal_info(account_address: str, issuer_address: str, data: dict, custom_personal_info_address=None,
                             default_value=""):
        """
        トークン保有者情報の修正

        :param account_address: アカウントアドレス
        :param issuer_address: 発行体のアドレス
        :param data: 更新データ
        :param custom_personal_info_address: 個人情報を格納している個人情報コントラクトのアドレス。
            未指定の場合はシステムデフォルトの個人情報コントラクトアドレスを使用する。
        :param default_value: 値が未設定の項目に設定する初期値。(未指定時: '--')
        :return:
        :raises HTTPException:
            コンソーシアム企業一覧にETH_ACCOUNTが設定されていない場合、HTTPステータス400で例外を発生させる。
        """

        # アドレスフォーマットのチェック
        if not Web3.isAddress(account_address):
            abort(404)

        # デフォルト値
        personal_info_default = {
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
        personal_info_data = json.dumps(TokenUtils.validateDictStruct(personal_info_default, data))

        # 個人情報暗号化用RSA公開鍵の取得
        issuer = Issuer.query.filter(Issuer.eth_account == issuer_address).first()
        rsa_public_key = None
        if Config.APP_ENV == 'production':  # Production環境の場合
            company_list = []
            isExist = False
            try:
                company_list = requests.get(Config.COMPANY_LIST_URL[issuer.network]).json()
            except Exception as err:
                logger.exception(f"{err}")
                abort(500)
            for company_info in company_list:
                if to_checksum_address(company_info['address']) == issuer_address:
                    isExist = True
                    rsa_public_key = RSA.importKey(company_info['rsa_publickey'].replace('\\n', ''))
            if not isExist:  # RSA公開鍵が取得できなかった場合はエラーを返して以降の処理を実施しない
                abort(400)
        else:  # NOTE:Production環境以外の場合はローカルのRSA公開鍵を取得
            rsa_public_key = RSA.importKey(open('data/rsa/public.pem').read())

        cipher = PKCS1_OAEP.new(rsa_public_key)
        ciphertext = base64.encodebytes(cipher.encrypt(personal_info_data.encode('utf-8')))

        # PersonalInfo情報更新
        if custom_personal_info_address is None:
            issuer = Issuer.query.filter(Issuer.eth_account == issuer_address).first()
            personal_info_address = issuer.personal_info_contract_address
        else:
            personal_info_address = to_checksum_address(custom_personal_info_address)
        PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', personal_info_address)
        try:
            tx = PersonalInfoContract.functions.modify(account_address, ciphertext). \
                buildTransaction({'from': issuer_address, 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=issuer_address)
        except Exception as err:
            logger.exception(f"{err}")
            raise EthRuntimeError()

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
