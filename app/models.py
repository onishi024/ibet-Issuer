# -*- coding:utf-8 -*-
from sqlalchemy.orm import deferred
from werkzeug.security import generate_password_hash, check_password_hash
from flask import url_for, redirect
from flask_login import UserMixin
from . import db, login_manager
from datetime import datetime
from enum import Enum


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
    # EOA秘密鍵保存先のパスワード（暗号化済）
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
    """債券保有者名簿"""
    __tablename__ = 'holder_list'

    # シーケンスID
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # トークンアドレス
    token_address = db.Column(db.String(42))
    # 保有者リスト（CSV）
    holder_list = db.Column(db.LargeBinary)
    # 作成タイムスタンプ
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AddressType(Enum):
    """アドレス種別"""
    OTHERS = 0
    ISSUER = 1
    EXCHANGE = 2


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
