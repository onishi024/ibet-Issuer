"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

import re
from http import HTTPStatus

from flask_jwt import jwt_required, current_identity
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app import db
from app.models import Transfer, HolderList, Issuer, User
from app.models import PersonalInfo as PersonalInfoModel
from app.utils import ContractUtils, TokenUtils
from config import Config
from . import api

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

from logging import getLogger
logger = getLogger('api')

DEFAULT_VALUE = "--"


@api.route('/share/holders/<string:token_address>', methods=['POST'])
@jwt_required()
def share_holders(token_address):
    """
    株式_保有者一覧取得
    :param token_address: トークンアドレス
    """
    logger.info('api/share/holders')

    # API実行ユーザの取得
    # LocalProxy (current_identity) のままSQLAlchemyに渡すとエラーになるためプロキシ先オブジェクトを取得する
    user_id = current_identity._get_current_object()
    user = User.query.get(user_id)
    issuer = Issuer.query.filter(Issuer.eth_account == user.eth_account).first()

    # トークン情報の取得
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=user.eth_account,
        template_id=Config.TEMPLATE_ID_SHARE
    )
    try:
        token_name = TokenContract.functions.name().call()
    except Exception as e:
        logger.exception(e)
        token_name = ''

    # OTC取引コントラクト接続
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as err:
        logger.error(f"Failed to get token attributes: {err}")
        tradable_exchange = Config.ZERO_ADDRESS
    dex_contract = ContractUtils.get_contract('IbetOTCExchange', tradable_exchange)

    # Transferイベントを検索
    # →　残高を保有している可能性のあるアドレスを抽出
    # →　保有者リストをユニークにする
    transfer_events = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address).all()

    token_owner = TokenContract.functions.owner().call()  # トークン発行体アドレスを取得
    holders_temp = [token_owner]  # 発行体アドレスをリストに追加
    for event in transfer_events:
        holders_temp.append(event.account_address_to)

    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    # 保有者情報抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        try:
            commitment = dex_contract.functions.commitmentOf(account_address, token_address).call()
        except Exception as e:
            logger.warning(e)
            commitment = 0

        if balance > 0 or commitment > 0:  # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
            # 保有者情報：デフォルト値（個人情報なし）
            holder = {
                'account_address': account_address,
                'key_manager': DEFAULT_VALUE,
                'name': DEFAULT_VALUE,
                'postal_code': DEFAULT_VALUE,
                'email': DEFAULT_VALUE,
                'address': DEFAULT_VALUE,
                'birth_date': DEFAULT_VALUE,
                'balance': balance,
                'commitment': commitment
            }

            if account_address == token_owner:  # 保有者が発行体の場合
                holder["name"] = issuer.issuer_name or '--'
            else:  # 保有者が発行体以外の場合
                record = PersonalInfoModel.query. \
                    filter(PersonalInfoModel.account_address == account_address). \
                    filter(PersonalInfoModel.issuer_address == token_owner). \
                    first()

                if record is not None:
                    decrypted_personal_info = record.personal_info
                    # 住所に含まれるUnicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                    address = decrypted_personal_info["address"]
                    formatted_address = \
                        re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)

                    holder = {
                        'account_address': account_address,
                        'key_manager': decrypted_personal_info["key_manager"],
                        'name': decrypted_personal_info["name"],
                        'postal_code': decrypted_personal_info["postal_code"],
                        'email': decrypted_personal_info["email"],
                        'address': formatted_address,
                        'birth_date': decrypted_personal_info["birth"],
                        'balance': balance,
                        'commitment': commitment
                    }

            # CSV出力用にトークンに関する情報を追加
            holder['token_name'] = token_name
            holder['token_address'] = token_address

            holders.append(holder)

    # CSV作成
    csv_columns = [
        'token_name',
        'token_address',
        'account_address',
        'key_manager',
        'balance',
        'commitment',
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


@api.route('/bond/holders/<string:token_address>', methods=['POST'])
@jwt_required()
def bond_holders(token_address):
    """
    債券_保有者一覧取得
    :param token_address: トークンアドレス
    """
    logger.info('api/bond/holders')

    # API実行ユーザの取得
    # LocalProxy (current_identity) のままSQLAlchemyに渡すとエラーになるためプロキシ先オブジェクトを取得する
    user_id = current_identity._get_current_object()
    user = User.query.get(user_id)
    issuer = Issuer.query.filter(Issuer.eth_account == user.eth_account).first()

    # トークン情報の取得
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=user.eth_account,
        template_id=Config.TEMPLATE_ID_SB
    )
    try:
        token_name = TokenContract.functions.name().call()
        face_value = TokenContract.functions.faceValue().call()
    except Exception as e:
        logger.exception(e)
        token_name = ''
        face_value = 0

    # DEXコントラクト接続
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as err:
        logger.error(f"Failed to get token attributes: {err}")
        tradable_exchange = Config.ZERO_ADDRESS
    dex_contract = ContractUtils.get_contract('IbetStraightBondExchange', tradable_exchange)

    # Transferイベントを検索
    # →　残高を保有している可能性のあるアドレスを抽出
    # →　保有者リストをユニークにする
    transfer_events = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address).all()

    token_owner = TokenContract.functions.owner().call()  # トークン発行体アドレスを取得
    holders_temp = [token_owner]  # 発行体アドレスをリストに追加
    for event in transfer_events:
        holders_temp.append(event.account_address_to)

    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    # 保有者情報抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        try:
            commitment = dex_contract.functions.commitmentOf(account_address, token_address).call()
        except Exception as e:
            logger.warning(e)
            commitment = 0

        if balance > 0 or commitment > 0:  # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
            # 保有者情報：デフォルト値（個人情報なし）
            holder = {
                'account_address': account_address,
                'key_manager': DEFAULT_VALUE,
                'name': DEFAULT_VALUE,
                'postal_code': DEFAULT_VALUE,
                'email': DEFAULT_VALUE,
                'address': DEFAULT_VALUE,
                'birth_date': DEFAULT_VALUE,
                'balance': balance,
                'commitment': commitment
            }

            if account_address == token_owner:  # 保有者が発行体の場合
                holder["name"] = issuer.issuer_name or '--'
            else:  # 保有者が発行体以外の場合
                record = PersonalInfoModel.query. \
                    filter(PersonalInfoModel.account_address == account_address). \
                    filter(PersonalInfoModel.issuer_address == token_owner). \
                    first()

                if record is not None:
                    decrypted_personal_info = record.personal_info
                    # 住所に含まれるUnicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                    address = decrypted_personal_info["address"]
                    formatted_address = \
                        re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)

                    holder = {
                        'account_address': account_address,
                        'key_manager': decrypted_personal_info["key_manager"],
                        'name': decrypted_personal_info["name"],
                        'postal_code': decrypted_personal_info["postal_code"],
                        'email': decrypted_personal_info["email"],
                        'address': formatted_address,
                        'birth_date': decrypted_personal_info["birth"],
                        'balance': balance,
                        'commitment': commitment
                    }

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
        'key_manager',
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


@api.route('/membership/holders/<string:token_address>', methods=['POST'])
@jwt_required()
def membership_holders(token_address):
    """
    会員権_保有者一覧取得
    :param token_address: トークンアドレス
    """
    logger.info('api/membership/holders')

    # API実行ユーザの取得
    # LocalProxy (current_identity) のままSQLAlchemyに渡すとエラーになるためプロキシ先オブジェクトを取得する
    user_id = current_identity._get_current_object()
    user = User.query.get(user_id)
    issuer = Issuer.query.filter(Issuer.eth_account == user.eth_account).first()

    # トークン情報の取得
    TokenContract = TokenUtils.get_contract(
        token_address=token_address,
        issuer_address=user.eth_account,
        template_id=Config.TEMPLATE_ID_MEMBERSHIP
    )
    try:
        token_name = TokenContract.functions.name().call()
    except Exception as e:
        logger.exception(e)
        token_name = ''

    # 会員権取引コントラクト接続
    try:
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as err:
        logger.error(f"Failed to get token attributes: {err}")
        tradable_exchange = Config.ZERO_ADDRESS
    dex_contract = ContractUtils.get_contract('IbetMembershipExchange', tradable_exchange)

    # Transferイベントを検索
    # →　残高を保有している可能性のあるアドレスを抽出
    # →　保有者リストをユニークにする
    transfer_events = Transfer.query. \
        distinct(Transfer.account_address_to). \
        filter(Transfer.token_address == token_address).all()

    token_owner = TokenContract.functions.owner().call()  # トークン発行体アドレスを取得
    holders_temp = [token_owner]  # 発行体アドレスをリストに追加
    for event in transfer_events:
        holders_temp.append(event.account_address_to)

    holders_uniq = []
    for x in holders_temp:
        if x not in holders_uniq:
            holders_uniq.append(x)

    # 保有者情報抽出
    holders = []
    for account_address in holders_uniq:
        balance = TokenContract.functions.balanceOf(account_address).call()
        try:
            commitment = dex_contract.functions.commitmentOf(account_address, token_address).call()
        except Exception as e:
            logger.warning(e)
            commitment = 0

        if balance > 0 or commitment > 0:  # 残高（balance）、または注文中の残高（commitment）が存在する情報を抽出
            # 保有者情報：デフォルト値（個人情報なし）
            holder = {
                'account_address': account_address,
                'key_manager': DEFAULT_VALUE,
                'name': DEFAULT_VALUE,
                'postal_code': DEFAULT_VALUE,
                'email': DEFAULT_VALUE,
                'address': DEFAULT_VALUE,
                'birth_date': DEFAULT_VALUE,
                'balance': balance,
                'commitment': commitment
            }

            if account_address == token_owner:  # 保有者が発行体の場合
                holder["name"] = issuer.issuer_name or '--'
            else:  # 保有者が発行体以外の場合
                record = PersonalInfoModel.query. \
                    filter(PersonalInfoModel.account_address == account_address). \
                    filter(PersonalInfoModel.issuer_address == token_owner). \
                    first()
                if record is not None:
                    decrypted_personal_info = record.personal_info
                    # 住所に含まれるUnicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                    address = decrypted_personal_info["address"]
                    formatted_address = \
                        re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)

                    holder = {
                        'account_address': account_address,
                        'key_manager': decrypted_personal_info["key_manager"],
                        'name': decrypted_personal_info["name"],
                        'postal_code': decrypted_personal_info["postal_code"],
                        'email': decrypted_personal_info["email"],
                        'address': formatted_address,
                        'birth_date': decrypted_personal_info["birth"],
                        'balance': balance,
                        'commitment': commitment
                    }

            # CSV出力用にトークンに関する情報を追加
            holder['token_name'] = token_name
            holder['token_address'] = token_address

            holders.append(holder)

    # CSV作成
    csv_columns = [
        'token_name',
        'token_address',
        'account_address',
        'key_manager',
        'balance',
        'commitment',
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
