#!/usr/local/bin/python
# -*- coding:utf-8 -*-
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager
from datetime import datetime

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
    return User.query.get(int(user_id))

class Token(db.Model):
    __tablename__ = 'tokens'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, nullable=False)
    tx_hash = db.Column(db.String(128), nullable=False)
    admin_address = db.Column(db.String(64), nullable=True)
    token_address = db.Column(db.String(64), nullable=True)
    abi = db.Column(db.String(20480), nullable=False)
    bytecode = db.Column(db.String(20480), nullable=False)
    bytecode_runtime = db.Column(db.String(20480), nullable=False)
    created = db.Column(db.DateTime, nullable=False, default=datetime.now)
    modified = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return "<Token(admin_address='%s',template_id='%i'," + \
            "'tx_hash'='%s', 'token_address'='%s'," + \
            "'abi'='%s', 'bytecode'='%s','bytecode_runtime'='%s')>" % \
            (self.admin_address, self.template_id, self.tx_hash, self.token_address,
                self.abi, self.bytecode, self.bytecode_runtime)

    @classmethod
    def get_id(cls):
        return Token.id

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
