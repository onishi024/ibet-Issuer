#!/usr/local/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import logging

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ZwiTDW52gQlxBQ8Sn34KYaLNQxA0mvpT2_RjYH5j-ZU='
    SSL_DISABLE = False
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    NAVI_MENU = {
        'admin': [
            ('account', 'glyphicon glyphicon-user', 'アカウント管理', [
                ('account_list', 'fa fa-list', 'アカウント一覧', 'account.list'),
                ('account_regist', 'fa fa-user-plus', 'アカウント追加', 'account.regist'),
            ]),
        ]
    }

    NAVI_MENU_USER = [
        ('token', 'glyphicon glyphicon-list-alt', '債券発行管理', [
            ('token_list', 'fa fa-ticket', '発行済債券一覧', 'token.list'),
            ('token_issue', 'fa fa-ticket', '債券新規発行', 'token.issue'),
        ]),
    ]

    NAVI_MENU_ADMIN = [
        ('account', 'glyphicon glyphicon-user', 'アカウント管理', [
            ('account_list', 'fa fa-list', 'アカウント一覧', 'account.list'),
        ]),
    ]

    LOG_CONFIG = ({
        'version': 1,
        'formatters': {'default': {
                'format': 'WEBAPL [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s [in %(pathname)s:%(lineno)d]',
        }},
        'handlers': {'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
                'formatter': 'default'
        }},
        'loggers': {
            'api': {
                'handlers': ['console',],
                'propagate': False,
        }},
        'root': {
            'level': 'DEBUG',
        }
    })

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'

class TestingConfig(Config):
    TESTING = True
    LOGIN_DISABLED = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb_test'

# seleniumのテストの際にFlaskを起動する時にのみ必要(そうしないとログイン画面が出てこない)
class SeleniumConfig(TestingConfig):
    LOGIN_DISABLED = False

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'

    LOG_CONFIG = ({
        'version': 1,
        'formatters': {'default': {
                'format': 'WEBAPL [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s',
        }},
        'handlers': {'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
                'formatter': 'default'
        }},
        'loggers': {
            'api': {
                'handlers': ['console',],
                'propagate': False,
        }},
        'root': {
            'level': 'WARNING',
        }
    })

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)

class UnixConfig(ProductionConfig):
    @classmethod
    def init_app(cls, app):
        ProductionConfig.init_app(app)

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'selenium': SeleniumConfig,
    'production': ProductionConfig,
    'unix': UnixConfig,
    'default': DevelopmentConfig
}
