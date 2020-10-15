#!/usr/local/bin/python
# -*- coding:utf-8 -*-
import os
import sys
from datetime import timedelta

from web3 import Web3

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Tokenテーブルのtemplate_id
    TEMPLATE_ID_SB = 1  # 債券
    TEMPLATE_ID_COUPON = 2  # クーポン
    TEMPLATE_ID_MEMBERSHIP = 3  # 会員権
    TEMPLATE_ID_SHARE = 4  # 株式

    # gunicornのworker数
    WORKER_COUNT = int(os.environ.get("WORKER_COUNT")) if os.environ.get("WORKER_COUNT") else 4

    # 実行環境
    APP_ENV = os.getenv('FLASK_CONFIG') or 'default'

    # Company List
    COMPANY_LIST_URL = {}
    if APP_ENV == "production":
        COMPANY_LIST_URL['IBET'] = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list/company_list.json'
        COMPANY_LIST_URL['IBETFIN'] = 'https://s3-ap-northeast-1.amazonaws.com/ibet-fin-company-list/company_list.json'
    else:
        COMPANY_LIST_URL['IBET'] = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list-dev/company_list.json'
        COMPANY_LIST_URL['IBETFIN'] = 'https://s3-ap-northeast-1.amazonaws.com/ibet-fin-company-list-dev/company_list.json'

    # SSL
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ZwiTDW52gQlxBQ8Sn34KYaLNQxA0mvpT2_RjYH5j-ZU='
    SSL_DISABLE = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # JWT (JSON Web Token)
    JWT_AUTH_URL_RULE = '/api/auth'
    JWT_AUTH_USERNAME_KEY = 'login_id'

    # Database / SQL Alchemy
    SQLALCHEMY_DATABASE_URI = \
        os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    # Navigation Menu
    NAVI_MENU = {
        'admin': [
            ('account', 'glyphicon glyphicon-user', 'アカウント管理', [
                ('account_list', 'fa fa-list', 'アカウント一覧', 'account.list'),
                ('account_regist', 'fa fa-user-plus', 'アカウント追加', 'account.regist'),
            ]),
        ]
    }

    NAVI_MENU_USER = [
        ('share', 'glyphicon glyphicon-th', '株式', [
            ('share_issue', 'fa fa-circle-o', '新規発行', 'share.issue'),
            ('share_list', 'fa fa-circle-o', '発行済一覧', 'share.list')
        ]),
        ('bond', 'glyphicon glyphicon-th', '債券', [
            ('bond_issue', 'fa fa-circle-o', '新規発行', 'bond.issue'),
            ('bond_list', 'fa fa-circle-o', '発行済一覧', 'bond.list'),
            ('bond_position', 'fa fa-circle-o', '売出管理', 'bond.positions'),
            ('bond_ledger_administrator', 'fa fa-circle-o', '原簿管理者情報', 'bond.ledger_administrator'),
        ]),
        ('membership', 'glyphicon glyphicon-th', '会員権', [
            ('membership_issue', 'fa fa-circle-o', '新規発行', 'membership.issue'),
            ('membership_list', 'fa fa-circle-o', '発行済一覧', 'membership.list'),
            ('membership_position', 'fa fa-circle-o', '売出管理', 'membership.positions'),
        ]),
        ('coupon', 'glyphicon glyphicon-th', 'クーポン', [
            ('coupon_issue', 'fa fa-circle-o', '新規発行', 'coupon.issue'),
            ('coupon_list', 'fa fa-circle-o', '発行済一覧', 'coupon.list'),
            ('coupon_position', 'fa fa-circle-o', '売出管理', 'coupon.positions'),
            ('coupon_transfer', 'fa fa-circle-o', '割当', 'coupon.transfer'),
            ('coupon_bulk_transfer', 'fa fa-circle-o', 'CSV一括割当', 'coupon.bulk_transfer')
        ]),
    ]

    NAVI_MENU_ADMIN = [
        ('account', 'glyphicon glyphicon-cog', 'Settings', [
            ('account_list', 'fa fa-circle-o', 'アカウント管理', 'account.list'),
            ('account_bank_info', 'fa fa-circle-o', '銀行口座情報', 'account.bankinfo'),
            ('account_issuer_info', 'fa fa-circle-o', '発行体情報', 'account.issuerinfo'),
        ]),
    ]

    # Logging
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
                'handlers': ['console', ],
                'propagate': False,
            }},
        'root': {
            'level': 'DEBUG',
        }
    })

    # Web3
    WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
    web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

    # Transaction Gas Limit
    TX_GAS_LIMIT = int(os.environ.get("TX_GAS_LIMIT")) if os.environ.get("TX_GAS_LIMIT") else 6000000

    # DBカラムIssuer.encrypted_account_passwordの鍵
    ETH_ACCOUNT_PASSWORD_SECRET_KEY = os.environ.get('ETH_ACCOUNT_PASSWORD_SECRET_KEY')

    # Private Key Store for AWS Secrets Manager
    AWS_REGION_NAME = 'ap-northeast-1'  # NOTE:現状は固定で設定
    AWS_SECRET_ID = os.environ.get('AWS_SECRET_ID')

    # RSA鍵ファイルのパスワード
    RSA_PASSWORD = os.environ.get('RSA_PASSWORD')

    # Zero Address
    ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    LOGIN_DISABLED = True
    SQLALCHEMY_DATABASE_URI = \
        os.environ.get('TEST_DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb_test'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
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
                'handlers': ['console', ],
                'propagate': False,
            }},
        'root': {
            'level': 'INFO',
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
    'production': ProductionConfig,
    'unix': UnixConfig,
    'default': DevelopmentConfig
}
