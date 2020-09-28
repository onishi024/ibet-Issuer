# -*- coding:utf-8 -*-
import re
from http import HTTPStatus

from flask_jwt import jwt_required, current_identity
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app import db
from app.models import Transfer, HolderList, Issuer, User
from app.utils import ContractUtils, TokenUtils
from config import Config
from . import api

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

from logging import getLogger

logger = getLogger('api')


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

    # トークン情報の取得
    TokenContract = TokenUtils.get_contract(token_address, user.eth_account, template_id=Config.TEMPLATE_ID_SHARE)
    try:
        token_name = TokenContract.functions.name().call()
        tradable_exchange = TokenContract.functions.tradableExchange().call()
        personal_info_address = TokenContract.functions.personalInfoAddress().call()
    except Exception as e:
        logger.exception(e)
        token_name = ''
        tradable_exchange = '0x0000000000000000000000000000000000000000'
        personal_info_address = '0x0000000000000000000000000000000000000000'
        pass

    # OTC取引コントラクト接続
    ExchangeContract = ContractUtils.get_contract('IbetOTCExchange', tradable_exchange)

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
                # 保有者が発行体以外の場合、個人情報コントラクトからトークン保有者の個人情報を取得する
                personal_info = TokenUtils.get_holder(
                    account_address,
                    user.eth_account,
                    custom_personal_info_address=personal_info_address,
                    default_value=''
                )

                name = personal_info['name'] if personal_info['name'] else "--"
                if personal_info['address']['prefecture'] and personal_info['address']['city'] and \
                        personal_info['address']['address1']:
                    address = personal_info['address']['prefecture'] + personal_info['address']['city']
                    if personal_info['address']['address1'] != "":
                        address = address + "　" + personal_info['address']['address1']
                    if personal_info['address']['address2'] != "":
                        address = address + "　" + personal_info['address']['address2']
                    # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                    address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)
                else:
                    address = "--"
                postal_code = personal_info['address']['postal_code'] if personal_info['address'][
                    'postal_code'] else "--"
                email = personal_info['email'] if personal_info['email'] else "--"
                birth_date = personal_info['birth'] if personal_info['birth'] else "--"

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

            # CSV出力用にトークンに関する情報を追加
            holder['token_name'] = token_name
            holder['token_address'] = token_address

            holders.append(holder)

    # CSV作成
    csv_columns = [
        'token_name',
        'token_address',
        'account_address',
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

    # トークン情報の取得
    TokenContract = TokenUtils.get_contract(token_address, user.eth_account, template_id=Config.TEMPLATE_ID_SB)
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
                # 保有者が発行体以外の場合、個人情報コントラクトからトークン保有者の個人情報を取得する
                personal_info = TokenUtils.get_holder(
                    account_address,
                    user.eth_account,
                    custom_personal_info_address=personal_info_address,
                    default_value=''
                )

                name = personal_info['name'] if personal_info['name'] else "--"
                if personal_info['address']['prefecture'] and personal_info['address']['city'] and \
                        personal_info['address']['address1']:
                    address = personal_info['address']['prefecture'] + personal_info['address']['city']
                    if personal_info['address']['address1'] != "":
                        address = address + "　" + personal_info['address']['address1']
                    if personal_info['address']['address2'] != "":
                        address = address + "　" + personal_info['address']['address2']
                    # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                    address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)
                else:
                    address = "--"
                postal_code = personal_info['address']['postal_code'] if personal_info['address'][
                    'postal_code'] else "--"
                email = personal_info['email'] if personal_info['email'] else "--"
                birth_date = personal_info['birth'] if personal_info['birth'] else "--"

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

    # トークン情報の取得
    TokenContract = TokenUtils.get_contract(token_address, user.eth_account, template_id=Config.TEMPLATE_ID_MEMBERSHIP)
    try:
        token_name = TokenContract.functions.name().call()
        tradable_exchange = TokenContract.functions.tradableExchange().call()
    except Exception as e:
        logger.exception(e)
        token_name = ''
        tradable_exchange = '0x0000000000000000000000000000000000000000'
        pass

    # 会員権取引コントラクト接続
    ExchangeContract = ContractUtils.get_contract('IbetMembershipExchange', tradable_exchange)

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
                # 保有者が発行体以外の場合、個人情報コントラクトからトークン保有者の個人情報を取得する
                personal_info = TokenUtils.get_holder(
                    account_address,
                    user.eth_account,
                    default_value=''
                )

                name = personal_info['name'] if personal_info['name'] else "--"
                if personal_info['address']['prefecture'] and personal_info['address']['city'] and \
                        personal_info['address']['address1']:
                    address = personal_info['address']['prefecture'] + personal_info['address']['city']
                    if personal_info['address']['address1'] != "":
                        address = address + "　" + personal_info['address']['address1']
                    if personal_info['address']['address2'] != "":
                        address = address + "　" + personal_info['address']['address2']
                    # Unicodeの各種ハイフン文字を半角ハイフン（U+002D）に変換する
                    address = re.sub('\u2010|\u2011|\u2012|\u2013|\u2014|\u2015|\u2212|\uff0d', '-', address)
                else:
                    address = "--"
                postal_code = personal_info['address']['postal_code'] if personal_info['address'][
                    'postal_code'] else "--"
                email = personal_info['email'] if personal_info['email'] else "--"
                birth_date = personal_info['birth'] if personal_info['birth'] else "--"

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

            # CSV出力用にトークンに関する情報を追加
            holder['token_name'] = token_name
            holder['token_address'] = token_address

            holders.append(holder)

    # CSV作成
    csv_columns = [
        'token_name',
        'token_address',
        'account_address',
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
