#!/usr/local/bin/python
# -*- coding:utf-8 -*-
from werkzeug.security import generate_password_hash, check_password_hash
from flask import url_for, redirect
from flask_login import UserMixin
from . import db, login_manager
from datetime import datetime
from enum import Enum


class AlembicVersion(db.Model):
    __tablename__ = 'alembic_version'
    id = db.Column(db.Integer, primary_key=True)


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    users = db.relationship('User', backref='role', lazy='dynamic')
    created = db.Column(db.DateTime, nullable=False, default=datetime.now)
    modified = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return '<Role %r>' % self.name


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.String(64), unique=True, index=True)
    user_name = db.Column(db.String(64), unique=False, index=True)
    icon = db.Column(db.LargeBinary)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    created = db.Column(db.DateTime, nullable=False, default=datetime.now)
    modified = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

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


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        pass


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('auth.login'))


class Token(db.Model):
    __tablename__ = 'tokens'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, nullable=False)
    tx_hash = db.Column(db.String(128), nullable=False)
    admin_address = db.Column(db.String(64), nullable=True)
    token_address = db.Column(db.String(64), nullable=True)
    abi = db.Column(db.String(20480), nullable=False)
    bytecode = db.Column(db.String(30720), nullable=False)
    bytecode_runtime = db.Column(db.String(30720), nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=datetime.now)
    modified = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return "<Token(admin_address='%s',template_id='%i','tx_hash'='%s','token_address'='%s','abi'='%s','bytecode'='%s','bytecode_runtime'='%s')>" % \
               (self.admin_address, self.template_id, self.tx_hash, self.token_address,
                self.abi, self.bytecode, self.bytecode_runtime)

    @classmethod
    def get_id(cls):
        return Token.id


# 割当一括登録（クーポン）
class CouponBulkTransfer(db.Model):
    __tablename__ = 'coupon_bulk_transfer'
    id = db.Column(db.Integer, primary_key=True)
    token_address = db.Column(db.String(42), nullable=False)
    to_address = db.Column(db.String(42), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    transferred = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return "<CouponBulkTransfer('token_address'='%s', 'to_address'='%s', 'amount'='%s', 'transferred'='%s')>" % \
               (self.token_address, self.to_address, self.amount, self.transferred)

    @classmethod
    def get_id(cls):
        return CouponBulkTransfer.id


# トークン認定依頼
class Certification(db.Model):
    __tablename__ = 'certification'
    id = db.Column(db.Integer, primary_key=True)
    token_address = db.Column(db.String(64), nullable=True)
    signer = db.Column(db.String(64), nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.now)
    modified = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return "<Certification(token_address='%s',signer='%s')>" % \
               (self.token_address, self.signer)

    @classmethod
    def get_id(cls):
        return Certification.id


# 銀行口座情報
class Bank(db.Model):
    __tablename__ = 'bank'
    id = db.Column(db.Integer, primary_key=True)
    eth_account = db.Column(db.String(50), nullable=False)
    bank_name = db.Column(db.String(40), nullable=False)
    bank_code = db.Column(db.String(4), nullable=False)
    branch_name = db.Column(db.String(40), nullable=False)
    branch_code = db.Column(db.String(3), nullable=False)
    account_type = db.Column(db.String(10), nullable=False)
    account_number = db.Column(db.String(7), nullable=False)
    account_holder = db.Column(db.String(40), nullable=False)

    def __repr__(self):
        return '<Bank %s>' % self.eth_account


# 注文
class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token_address = db.Column(db.String(42), index=True)
    exchange_address = db.Column(db.String(42), index=True)
    order_id = db.Column(db.Integer, index=True)
    unique_order_id = db.Column(db.String(62), index=True)
    account_address = db.Column(db.String(42))
    is_buy = db.Column(db.Boolean)
    price = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    agent_address = db.Column(db.String(42))
    is_cancelled = db.Column(db.Boolean)

    def __repr__(self):
        return "<Order('token_address'='%s', 'exchange_address'='%s', 'order_id'='%i')>" % \
               (self.token_address, self.exchange_address, self.order_id)

    @classmethod
    def get_id(cls):
        return Order.id

# 約定
class Agreement(db.Model):
    __tablename__ = 'agreement'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    token_address = db.Column(db.String(42), index=True)
    exchange_address = db.Column(db.String(42), index=True)
    order_id = db.Column(db.Integer, index=True)
    agreement_id = db.Column(db.Integer, index=True)
    unique_order_id = db.Column(db.String(62), index=True)
    buyer_address = db.Column(db.String(42), index=True)
    seller_address = db.Column(db.String(42), index=True)
    price = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    agent_address = db.Column(db.String(42))
    status = db.Column(db.Integer)

    def __repr__(self):
        return "<Agreement('token_address'='%s', 'exchange_address'='%s', 'order_id'='%i', 'agreement_id'='%i')>" % \
               (self.token_address, self.exchange_address, self.order_id, self.agreement_id)

    @classmethod
    def get_id(cls):
        return Agreement.id

# 約定ステータス
class AgreementStatus(Enum):
    PENDING = 0
    DONE = 1
    CANCELED = 2


# トークン移転履歴（Event）
class Transfer(db.Model):
    __tablename__ = 'transfer'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    transaction_hash = db.Column(db.String(66), index=True)
    token_address = db.Column(db.String(42), index=True)
    account_address_from = db.Column(db.String(42), index=True)
    account_address_to = db.Column(db.String(42), index=True)
    transfer_amount = db.Column(db.Integer)
    block_timestamp = db.Column(db.DateTime)

    def __repr__(self):
        return "<Transfer('transaction_hash'='%s', 'token_address'='%s')>" % \
               (self.transaction_hash, self.token_address)

    @classmethod
    def get_id(cls):
        return Transfer.id


# アドレスタイプ
class AddressType(Enum):
    OTHERS = 0
    ISSUER = 1
    EXCHANGE = 2