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

import base64
import json
from datetime import datetime
from enum import Enum

import requests
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from sqlalchemy.orm import deferred
from werkzeug.security import generate_password_hash, check_password_hash
from flask import url_for, redirect, abort
from flask_login import UserMixin
from eth_utils import to_checksum_address
from web3 import Web3
from web3.middleware import geth_poa_middleware

from . import db, login_manager
from config import Config
from logging import getLogger

from .exceptions import EthRuntimeError
from .utils import ContractUtils

logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        pass


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('auth.login'))


########################################################
# DBバージョン管理
########################################################
class AlembicVersion(db.Model):
    """Alembicバージョン管理"""
    __tablename__ = 'alembic_version'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)


########################################################
# アカウント管理
########################################################
class Role(db.Model):
    """ロール定義"""
    __tablename__ = 'roles'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # ロール名
    name = db.Column(db.String(64), unique=True)
    # usersテーブルとのリレーション
    users = db.relationship('User', backref='role', lazy='dynamic')
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # 更新タイムスタンプ
    modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<Role %r>' % self.name


class User(UserMixin, db.Model):
    """ユーザ情報"""
    __tablename__ = 'users'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # アカウントアドレス
    eth_account = db.Column(db.String(42), nullable=False)
    # ログインID
    login_id = db.Column(db.String(64), unique=True, index=True)
    # ユーザー名
    user_name = db.Column(db.String(64), unique=False, index=True)
    # アイコン
    icon = db.Column(db.LargeBinary)
    # ロールID
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    # パスワード（ハッシュ）
    password_hash = db.Column(db.String(128))
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # 更新タイムスタンプ
    modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return '<User login_id={login_id} role_id={role_id}>'.format(
            login_id=self.login_id, role_id=self.role_id
        )

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


class Bank(db.Model):
    """払込用銀行口座情報"""
    __tablename__ = 'bank'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # アカウントアドレス
    eth_account = db.Column(db.String(50), nullable=False)
    # 金融機関名
    bank_name = db.Column(db.String(40), nullable=False)
    # 金融機関コード
    bank_code = db.Column(db.String(4), nullable=False)
    # 支店名
    branch_name = db.Column(db.String(40), nullable=False)
    # 支店コード
    branch_code = db.Column(db.String(3), nullable=False)
    # 口座種別
    account_type = db.Column(db.String(10), nullable=False)
    # 口座番号
    account_number = db.Column(db.String(7), nullable=False)
    # 口座名義
    account_holder = db.Column(db.String(40), nullable=False)

    def __repr__(self):
        return '<Bank %s>' % self.eth_account


class Issuer(db.Model):
    """発行体情報"""
    __tablename__ = 'issuer'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # アカウントアドレス
    eth_account = db.Column(db.String(50), unique=True, nullable=False)
    # 発行体名称
    issuer_name = db.Column(db.String(64), nullable=False)
    # 秘密鍵保存先（GETH or AWS_SECRETS_MANAGER)
    private_keystore = db.Column(db.String(64), nullable=False, default="GETH")
    # 一般/金融ネットワーク（IBET or IBETFIN）
    network = db.Column(db.String(64), nullable=False, default="IBET")
    # 売出価格（単価）の上限値（円）
    max_sell_price = db.Column(db.Integer, nullable=False, default=100000000)
    # 収納代行業者アドレス
    agent_address = db.Column(db.String(42))
    # PaymentGatewayコントラクトアドレス
    payment_gateway_contract_address = db.Column(db.String(42))
    # 個人情報記帳コントラクトアドレス
    personal_info_contract_address = db.Column(db.String(42))
    # トークンリストコントラクトアドレス
    token_list_contract_address = db.Column(db.String(42))
    # 株式取引コントラクトアドレス
    ibet_share_exchange_contract_address = db.Column(db.String(42))
    # 債券取引コントラクトアドレス
    ibet_sb_exchange_contract_address = db.Column(db.String(42))
    # 会員権取引コントラクトアドレス
    ibet_membership_exchange_contract_address = db.Column(db.String(42))
    # クーポン取引コントラクトアドレス
    ibet_coupon_exchange_contract_address = db.Column(db.String(42))
    # EOA keyfileのパスワード（暗号化済）
    # deferredで暗号化情報が必要なとき以外はDBから取得しないようにする
    encrypted_account_password = deferred(db.Column(db.String(2048)))
    # 個人情報復号化用RSA鍵ファイル（暗号化済）
    # deferredで暗号化情報が必要なとき以外はDBから取得しないようにする
    encrypted_rsa_private_key = deferred(db.Column(db.String(16384)))

    def __repr__(self):
        return '<Issuer %s>' % self.eth_account


########################################################
# トークン管理
########################################################
class Token(db.Model):
    """発行済トークン"""
    __tablename__ = 'tokens'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # トークン種別
    template_id = db.Column(db.Integer, nullable=False)
    # トランザクションハッシュ
    tx_hash = db.Column(db.String(128), nullable=False)
    # 発行体アドレス
    admin_address = db.Column(db.String(64), nullable=True)
    # トークンアドレス（コントラクトアドレス）
    token_address = db.Column(db.String(64), nullable=True)
    # ABI
    abi = db.Column(db.String(20480), nullable=False)
    # コントラクトバイトコード
    bytecode = db.Column(db.String(65536), nullable=False)
    # コントラクトランタイムコード
    bytecode_runtime = db.Column(db.String(65536), nullable=False)
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # 更新タイムスタンプ
    modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return "<Token(admin_address='%s',template_id='%i','tx_hash'='%s','token_address'='%s','abi'='%s','bytecode'='%s','bytecode_runtime'='%s')>" % \
               (self.admin_address, self.template_id, self.tx_hash, self.token_address,
                self.abi, self.bytecode, self.bytecode_runtime)

    @classmethod
    def get_id(cls):
        return Token.id


class CouponBulkTransfer(db.Model):
    """クーポン割当一括登録"""
    __tablename__ = 'coupon_bulk_transfer'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # アカウントアドレス
    eth_account = db.Column(db.String(42), nullable=False)
    # トークンアドレス
    token_address = db.Column(db.String(42), nullable=False)
    # 割当先アドレス
    to_address = db.Column(db.String(42), nullable=False)
    # 割当数量
    amount = db.Column(db.Integer, nullable=False)
    # 割当状態
    transferred = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return "<CouponBulkTransfer('token_address'='%s', 'to_address'='%s', 'amount'='%s', 'transferred'='%s')>" % \
               (self.token_address, self.to_address, self.amount, self.transferred)

    @classmethod
    def get_id(cls):
        return CouponBulkTransfer.id


class Certification(db.Model):
    """債券認定依頼"""
    __tablename__ = 'certification'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # トークンアドレス
    token_address = db.Column(db.String(64), nullable=True)
    # 認定依頼先
    signer = db.Column(db.String(64), nullable=True)
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # 更新タイムスタンプ
    modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return "<Certification(token_address='%s',signer='%s')>" % \
               (self.token_address, self.signer)

    @classmethod
    def get_id(cls):
        return Certification.id


class HolderList(db.Model):
    """保有者名簿CSV"""
    __tablename__ = 'holder_list'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トークンアドレス
    token_address = db.Column(db.String(42))
    # 保有者リスト（CSV）
    holder_list = db.Column(db.LargeBinary)
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class UTXO(db.Model):
    """UTXO"""
    __tablename__ = "utxo"

    # トランザクションハッシュ
    transaction_hash = db.Column(db.String(66), primary_key=True)
    # アカウントアドレス
    account_address = db.Column(db.String(42), index=True)
    # トークンアドレス
    token_address = db.Column(db.String(42), index=True)
    # 数量
    amount = db.Column(db.Integer)
    # ブロックタイムスタンプ
    block_timestamp = db.Column(db.DateTime)
    # トランザクション年月日
    transaction_date_jst = db.Column(db.String(10))

    def __repr__(self):
        return f"<UTXO {self.transaction_hash}, {self.account_address}, {self.token_address}, {self.amount}>"


class BondLedger(db.Model):
    """債券原簿"""
    __tablename__ = "bond_ledger"

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トークンアドレス
    token_address = db.Column(db.String(42))
    # 原簿情報（JSON）
    ledger = db.Column(db.LargeBinary)
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class BondLedgerBlockNumber(db.Model):
    """債券原簿の同期済blockNumber"""
    __tablename__ = "bond_ledger_block_number"

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 直近blockNumber
    latest_block_number = db.Column(db.Integer)


class AddressType(Enum):
    """アドレス種別"""
    OTHERS = 0
    ISSUER = 1
    EXCHANGE = 2


class CorporateBondLedgerTemplate(db.Model):
    """社債原簿基本情報"""
    __tablename__ = 'corporate_bond_ledger_template'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # トークンアドレス
    token_address = db.Column(db.String(42), index=True)
    # アカウントアドレス
    eth_account = db.Column(db.String(42), index=True)
    # 社債名称
    bond_name = db.Column(db.String(200), nullable=False)
    # 社債の説明
    bond_description = db.Column(db.String(1000), nullable=False)
    # 社債の種類
    bond_type = db.Column(db.String(1000), nullable=False)
    # 社債の総額
    total_amount = db.Column(db.BigInteger, nullable=False)
    # 各社債の金額
    face_value = db.Column(db.Integer, nullable=False)
    # 払込情報_払込金額
    payment_amount = db.Column(db.BigInteger)
    # 払込情報_払込日
    payment_date = db.Column(db.String(8))
    # 払込情報_払込状況
    payment_status = db.Column(db.Boolean, nullable=False)
    # 原簿管理人_名称
    ledger_admin_name = db.Column(db.String(200), nullable=False)
    # 原簿管理人_住所
    ledger_admin_address = db.Column(db.String(200), nullable=False)
    # 原簿管理人_事務取扱場所
    ledger_admin_location = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<CorporateBondLedgerTemplate({self.token_address}, {self.eth_account})>'


########################################################
# ブロックチェーンイベントログ
########################################################
class Transfer(db.Model):
    """トークン移転イベント"""
    __tablename__ = 'transfer'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トランザクションハッシュ
    transaction_hash = db.Column(db.String(66), index=True)
    # トークンアドレス
    token_address = db.Column(db.String(42), index=True)
    # 移転元アドレス
    account_address_from = db.Column(db.String(42), index=True)
    # 移転先アドレス
    account_address_to = db.Column(db.String(42), index=True)
    # 移転数量
    transfer_amount = db.Column(db.Integer)
    # ブロックタイムスタンプ
    block_timestamp = db.Column(db.DateTime)

    def __repr__(self):
        return "<Transfer('transaction_hash'='%s', 'token_address'='%s')>" % \
               (self.transaction_hash, self.token_address)

    @classmethod
    def get_id(cls):
        return Transfer.id


class ApplyFor(db.Model):
    """募集申込イベント"""
    __tablename__ = 'apply_for'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トランザクションハッシュ
    transaction_hash = db.Column(db.String(66), index=True)
    # トークンアドレス
    token_address = db.Column(db.String(42), index=True)
    # アカウントアドレス
    account_address = db.Column(db.String(42), index=True)
    # 申込数量
    amount = db.Column(db.Integer)
    # ブロックタイムスタンプ
    block_timestamp = db.Column(db.DateTime)

    def __repr__(self):
        return "<ApplyFor('transaction_hash'='%s', 'token_address'='%s')>" % \
               (self.transaction_hash, self.token_address)

    @classmethod
    def get_id(cls):
        return ApplyFor.id


class Consume(db.Model):
    """トークン消費イベント"""
    __tablename__ = 'consume'

    # トランザクションハッシュ
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トークンアドレス
    transaction_hash = db.Column(db.String(66), index=True)
    # トークン消費者アドレス
    token_address = db.Column(db.String(42), index=True)
    # 消費者の保有トークン残高
    consumer_address = db.Column(db.String(42), index=True)
    # 消費者の保有トークン残高
    balance = db.Column(db.Integer)
    # 消費者の累計消費トークン数量
    total_used_amount = db.Column(db.Integer)
    # この消費イベントでの消費トークン数量
    used_amount = db.Column(db.Integer)
    # ブロックタイムスタンプ
    block_timestamp = db.Column(db.DateTime)

    def __repr__(self):
        return "<Consume('transaction_hash'='%s', 'token_address'='%s')>" % \
               (self.transaction_hash, self.token_address)

    @classmethod
    def get_id(cls):
        return Transfer.id


class Order(db.Model):
    """注文イベント"""
    __tablename__ = 'order'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トークンアドレス
    token_address = db.Column(db.String(42), index=True)
    # DEXアドレス
    exchange_address = db.Column(db.String(42), index=True)
    # 注文ID
    order_id = db.Column(db.Integer, index=True)
    # 注文ID（ユニーク）
    unique_order_id = db.Column(db.String(62), index=True)
    # 注文者アドレス
    account_address = db.Column(db.String(42))
    # 売買区分
    is_buy = db.Column(db.Boolean)
    # 注文単価
    price = db.Column(db.Integer)
    # 注文数量
    amount = db.Column(db.Integer)
    # 収納代行アドレス
    agent_address = db.Column(db.String(42))
    # 注文取消区分
    is_cancelled = db.Column(db.Boolean)

    def __repr__(self):
        return "<Order('token_address'='%s', 'exchange_address'='%s', 'order_id'='%i')>" % \
               (self.token_address, self.exchange_address, self.order_id)

    @classmethod
    def get_id(cls):
        return Order.id


class Agreement(db.Model):
    """約定イベント"""
    __tablename__ = 'agreement'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トークンアドレス
    token_address = db.Column(db.String(42), index=True)
    # DEXアドレス
    exchange_address = db.Column(db.String(42), index=True)
    # 注文ID
    order_id = db.Column(db.Integer, index=True)
    # 約定ID
    agreement_id = db.Column(db.Integer, index=True)
    # 注文ID（ユニーク）
    unique_order_id = db.Column(db.String(62), index=True)
    # 買い手アドレス
    buyer_address = db.Column(db.String(42), index=True)
    # 売り手アドレス
    seller_address = db.Column(db.String(42), index=True)
    # 約定単価
    price = db.Column(db.Integer)
    # 約定数量
    amount = db.Column(db.Integer)
    # 収納代行アドレス
    agent_address = db.Column(db.String(42))
    # 約定ステータス
    status = db.Column(db.Integer)

    def __repr__(self):
        return "<Agreement('token_address'='%s', 'exchange_address'='%s', 'order_id'='%i', 'agreement_id'='%i')>" % \
               (self.token_address, self.exchange_address, self.order_id, self.agreement_id)

    @classmethod
    def get_id(cls):
        return Agreement.id


class AgreementStatus(Enum):
    """約定ステータス"""
    PENDING = 0
    DONE = 1
    CANCELED = 2


########################################################
# 購入者情報
########################################################
class PersonalInfo(db.Model):
    """購入者個人情報（復号化済）"""
    __tablename__ = 'personalinfo'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True)
    # アカウントアドレス
    account_address = db.Column(db.String(42), index=True)
    # 発行体アドレス
    issuer_address = db.Column(db.String(42), index=True)
    # 個人情報
    personal_info = db.Column(db.JSON, nullable=False)
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.now)
    # 更新タイムスタンプ
    modified = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<PersonalInfo('account_address'={self.account_address}, 'issuer_address'={self.issuer_address}>"


class PersonalInfoBlockNumber(db.Model):
    """購入者個人情報の同期済blockNumber"""
    __tablename__ = "personalinfo_block_number"

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 直近blockNumber
    latest_block_number = db.Column(db.Integer)


########################################################
# コントラクト
########################################################
class PersonalInfoContract:
    """PersonalInfoコントラクト"""

    def __init__(self, issuer_address: str, custom_personal_info_address=None):
        issuer = Issuer.query. \
            filter(Issuer.eth_account == to_checksum_address(issuer_address)). \
            first()
        self.issuer = issuer

        if custom_personal_info_address is None:
            contract_address = issuer.personal_info_contract_address
        else:
            contract_address = to_checksum_address(custom_personal_info_address)
        contract_file = f"contracts/PersonalInfo.json"
        contract_json = json.load(open(contract_file, "r"))
        self.personal_info_contract = web3.eth.contract(
            address=to_checksum_address(contract_address),
            abi=contract_json['abi'],
        )

    def get_info(self, account_address: str, default_value=None):
        """個人情報取得

        :param account_address: トークン保有者のアドレス
        :param default_value: 値が未設定の項目に設定する初期値。(未指定時: None)
        :return: personal info
        """
        # アドレスフォーマットのチェック
        if not Web3.isAddress(account_address):
            abort(404)

        # 発行体のRSA秘密鍵の取得
        cipher = None
        try:
            key = RSA.importKey(self.issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
            cipher = PKCS1_OAEP.new(key)
        except Exception as err:
            logger.error(f"Cannot open the private key: {err}")

        # デフォルト値を設定
        personal_info = {
            "account_address": account_address,
            "key_manager": default_value,
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

        # 個人情報（暗号化）取得
        personal_info_state = self.personal_info_contract.functions. \
            personal_info(account_address, self.issuer.eth_account). \
            call()
        encrypted_info = personal_info_state[2]

        if encrypted_info == '' or cipher is None:
            return personal_info  # デフォルトの情報を返却
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
                decrypted_info = json.loads(cipher.decrypt(ciphertext))

                personal_info["key_manager"] = decrypted_info.get("key_manager", default_value)
                personal_info["name"] = decrypted_info.get("name", default_value)
                address = decrypted_info.get("address")
                if address is not None:
                    personal_info["address"]["postal_code"] = address.get("postal_code", default_value)
                    personal_info["address"]["prefecture"] = address.get("prefecture", default_value)
                    personal_info["address"]["city"] = address.get("city", default_value)
                    personal_info["address"]["address1"] = address.get("address1", default_value)
                    personal_info["address"]["address2"] = address.get("address2", default_value)
                personal_info["email"] = decrypted_info.get("email", default_value)
                personal_info["birth"] = decrypted_info.get("birth", default_value)
                return personal_info
            except Exception as err:
                logger.error(f"Failed to decrypt: {err}")
                return personal_info  # デフォルトの情報を返却

    def modify_info(self, account_address: str, data: dict, default_value=None):
        """トークン保有者情報の修正

        :param account_address: アカウントアドレス
        :param data: 更新データ
        :param default_value: 値が未設定の項目に設定する初期値。(未指定時: None)
        :return: None
        """
        # アドレスフォーマットのチェック
        if not Web3.isAddress(account_address):
            abort(404)

        # デフォルト値
        personal_info = {
            "key_manager": data.get("key_manager", default_value),
            "name": data.get("name", default_value),
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

        address = data.get("address")
        if address is not None:
            personal_info["address"]["postal_code"] = address.get("postal_code", default_value)
            personal_info["address"]["prefecture"] = address.get("prefecture", default_value)
            personal_info["address"]["city"] = address.get("city", default_value)
            personal_info["address"]["address1"] = address.get("address1", default_value)
            personal_info["address"]["address2"] = address.get("address2", default_value)
        personal_info["email"] = data.get("email", default_value)
        personal_info["birth"] = data.get("birth", default_value)

        # 個人情報暗号化用RSA公開鍵の取得
        rsa_public_key = None
        if Config.APP_ENV == 'production':  # Production環境の場合
            company_list = []
            isExist = False
            try:
                company_list = requests.get(Config.COMPANY_LIST_URL[self.issuer.network]).json()
            except Exception as err:
                logger.exception(f"{err}")
                abort(500)
            for company_info in company_list:
                if to_checksum_address(company_info['address']) == self.issuer.eth_account:
                    isExist = True
                    rsa_public_key = RSA.importKey(company_info['rsa_publickey'].replace('\\n', ''))
            if not isExist:  # RSA公開鍵が取得できなかった場合はエラーを返して以降の処理を実施しない
                abort(400)
        else:  # NOTE:Production環境以外の場合はローカルのRSA公開鍵を取得
            rsa_public_key = RSA.importKey(open('data/rsa/public.pem').read())

        # 個人情報の暗号化
        cipher = PKCS1_OAEP.new(rsa_public_key)
        ciphertext = base64.encodebytes(cipher.encrypt(json.dumps(personal_info).encode('utf-8')))

        try:
            tx = self.personal_info_contract.functions.modify(account_address, ciphertext). \
                buildTransaction({'from': self.issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=self.issuer.eth_account)
        except Exception as err:
            logger.exception(f"{err}")
            raise EthRuntimeError()
