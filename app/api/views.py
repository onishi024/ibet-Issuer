# -*- coding:utf-8 -*-
import base64
import json
import re
from http import HTTPStatus

from flask_jwt import jwt_required

from . import api
from .errors import bad_request, internal_server_error
from app import db
from app.models import Token, Transfer, HolderList, Issuer
from app.utils import ContractUtils
from config import Config

from web3 import Web3
from web3.middleware import geth_poa_middleware
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

from logging import getLogger
logger = getLogger('api')


@api.route('/bond/holders/<string:token_address>', methods=['POST'])
@jwt_required()
def bond_holders(token_address):
    """
    債券_保有者一覧取得
    :param token_address: トークンアドレス
    """
    logger.info('api/bond/holders')

    try:
        # RSA秘密鍵の取得
        cipher = None
        try:
            key = RSA.importKey(open('data/rsa/private.pem').read(), Config.RSA_PASSWORD)
            cipher = PKCS1_OAEP.new(key)
        except Exception as e:
            logger.exception(e)
            pass

        # Token情報取得
        token = Token.query.filter(Token.token_address == token_address).first()
        if token is None:
            return bad_request('Invalid token_address')
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))

        # Tokenコントラクト接続
        TokenContract = web3.eth.contract(address=token_address, abi=token_abi)

        # トークン情報の取得
        try:
            token_name = TokenContract.functions.name().call()
            face_value = TokenContract.functions.faceValue().call()
            tradable_exchange = TokenContract.functions.tradableExchange().call()
            personal_info_address = TokenContract.functions.personalInfoAddress().call()
        except Exception as e:
            logger.exception(e)
            token_name = ''
            face_value = 0
            tradable_exchange = '0x0000000000000000000000000000000000000000'
            personal_info_address = '0x0000000000000000000000000000000000000000'
            pass

        # 債券取引コントラクト接続
        ExchangeContract = ContractUtils.get_contract('IbetStraightBondExchange', tradable_exchange)

        # 個人情報コントラクト接続
        PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', personal_info_address)

        # Transferイベントを検索
        transfer_events = Transfer.query. \
            distinct(Transfer.account_address_to). \
            filter(Transfer.token_address == token_address).all()

        # 残高を保有している可能性のあるアドレスを抽出する
        token_owner = TokenContract.functions.owner().call()  # トークン発行体アドレスを取得
        holders_temp = [token_owner]  # 発行体アドレスをリストに追加
        for event in transfer_events:
            holders_temp.append(event.account_address_to)

        # 口座リストをユニークにする
        holders_uniq = []
        for x in holders_temp:
            if x not in holders_uniq:
                holders_uniq.append(x)

        # 保有者情報抽出
        holders = []
        for account_address in holders_uniq:
            balance = TokenContract.functions.balanceOf(account_address).call()
            try:
                commitment = ExchangeContract.functions.commitmentOf(account_address, token_address).call()
            except Exception as e:
                logger.warning(e)
                commitment = 0
                pass
            if balance > 0 or commitment > 0:  # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
                # 保有者情報：初期値（個人情報なし）
                holder = {
                    'account_address': account_address,
                    'name': '--',
                    'postal_code': '--',
                    'email': '--',
                    'address': '--',
                    'birth_date': '--',
                    'balance': balance,
                    'commitment': commitment
                }

                if account_address == token_owner:
                    # 保有者が発行体の場合
                    issuer_info = Issuer.query.filter(Issuer.eth_account == account_address).first()

                    if issuer_info is not None:
                        # 保有者情報（発行体）
                        holder = {
                            'account_address': account_address,
                            'name': issuer_info.issuer_name or '--',
                            'postal_code': '--',
                            'email': '--',
                            'address': '--',
                            'birth_date': '--',
                            'balance': balance,
                            'commitment': commitment
                        }
                else:
                    # 暗号化個人情報取得
                    try:
                        encrypted_info = PersonalInfoContract.functions.personal_info(account_address, token_owner).call()[2]
                    except Exception as e:
                        logger.warning(e)
                        encrypted_info = ''
                        pass

                    if encrypted_info == '' or cipher is None:  # 情報が空の場合、デフォルト値を設定
                        pass
                    else:
                        try:
                            # 個人情報復号化
                            ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                            message = cipher.decrypt(ciphertext)
                            personal_info_json = json.loads(message)

                            name = personal_info_json['name'] if personal_info_json['name'] else "--"
                            if personal_info_json['address']['prefecture'] and personal_info_json['address']['city'] and personal_info_json['address']['address1']:
                                address = personal_info_json['address']['prefecture'] + personal_info_json['address']['city']
                                if personal_info_json['address']['address1'] != "":
                                    address = address + "　" + personal_info_json['address']['address1']
                                if personal_info_json['address']['address2'] != "":
                                    address = address + "　" + personal_info_json['address']['address2']
                                # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                                address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)
                            else:
                                address = "--"
                            postal_code = personal_info_json['address']['postal_code'] if personal_info_json['address']['postal_code'] else "--"
                            email = personal_info_json['email'] if personal_info_json['email'] else "--"
                            birth_date = personal_info_json['birth'] if personal_info_json['birth'] else "--"

                            # 保有者情報（個人情報あり）
                            holder = {
                                'account_address': account_address,
                                'name': name,
                                'postal_code': postal_code,
                                'email': email,
                                'address': address,
                                'birth_date': birth_date,
                                'balance': balance,
                                'commitment': commitment
                            }
                        except Exception as e:  # 復号化処理でエラーが発生した場合、デフォルト値を設定
                            logger.exception(e)
                            pass

                # CSV出力用にトークンに関する情報を追加
                holder['token_name'] = token_name
                holder['token_address'] = token_address
                total_balance = holder['balance'] + holder['commitment']
                holder['total_balance'] = total_balance
                holder['total_holdings'] = total_balance * face_value

                holders.append(holder)

        # CSV作成
        csv_columns = [
            'token_name',
            'token_address',
            'account_address',
            'balance',
            'commitment',
            'total_balance',
            'total_holdings',
            'name',
            'birth_date',
            'postal_code',
            'address',
            'email'
        ]
        csv_data = '\n'.join([
            # CSVヘッダ行
            ','.join(csv_columns),
            # CSVデータ行
            *[','.join(map(lambda column: str(holder1[column]), csv_columns)) for holder1 in holders]
        ]) + '\n'

        # DBに登録
        holder_list = HolderList(token_address=token_address, holder_list=csv_data.encode('sjis', 'ignore'))
        db.session.add(holder_list)

        return '', HTTPStatus.CREATED

    except Exception as e:
        logger.exception(e)
        return internal_server_error()
