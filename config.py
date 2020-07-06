#!/usr/local/bin/python
# -*- coding:utf-8 -*-
import os
import sys
from datetime import timedelta
import qrcode

from web3 import Web3
from eth_utils import to_checksum_address

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Tokenテーブルのtemplate_id
    TEMPLATE_ID_SB = 1 # 債券
    TEMPLATE_ID_COUPON = 2 # クーポン
    TEMPLATE_ID_MEMBERSHIP = 3 # 会員権
    TEMPLATE_ID_SHARE = 4 # 株式

    # gunicornのworker数
    WORKER_COUNT = int(os.environ.get("WORKER_COUNT")) if os.environ.get("WORKER_COUNT") else 4

    # Company List
    APP_ENV = os.getenv('FLASK_CONFIG') or 'default'

    if APP_ENV == 'production':
        COMPANY_LIST_URL = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list/company_list.json'
    else:
        COMPANY_LIST_URL = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list-dev/company_list.json'

    if APP_ENV == 'production':
        PAYMENT_AGENT_LIST_URL = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list/payment_agent_list.json'
    else:
        PAYMENT_AGENT_LIST_URL = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list-dev/payment_agent_list.json'

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

    # EOA (Ethereum Account)
    if os.environ.get('ETH_ACCOUNT') is not None:
        ETH_ACCOUNT = to_checksum_address(os.environ.get('ETH_ACCOUNT'))
    else:
        ETH_ACCOUNT = web3.eth.accounts[0]

    ETH_ACCOUNT_PASSWORD = os.environ.get('ETH_ACCOUNT_PASSWORD')

    img = qrcode.make(ETH_ACCOUNT)
    img.save('app/static/eth_address.png')

    # TokenList-Contract
    TOKEN_LIST_CONTRACT_ADDRESS = ''
    if os.environ.get('TOKEN_LIST_CONTRACT_ADDRESS') is not None:
        TOKEN_LIST_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('TOKEN_LIST_CONTRACT_ADDRESS'))

    # PaymentGateway-Contract
    PAYMENT_GATEWAY_CONTRACT_ADDRESS = ''
    if os.environ.get('PAYMENT_GATEWAY_CONTRACT_ADDRESS') is not None:
        PAYMENT_GATEWAY_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('PAYMENT_GATEWAY_CONTRACT_ADDRESS'))

    # PersonalInfo-Contract
    PERSONAL_INFO_CONTRACT_ADDRESS = ''
    if os.environ.get('PERSONAL_INFO_CONTRACT_ADDRESS') is not None:
        PERSONAL_INFO_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('PERSONAL_INFO_CONTRACT_ADDRESS'))

    # IbetStraightBondExchange-Contract
    IBET_SB_EXCHANGE_CONTRACT_ADDRESS = ''
    if os.environ.get('IBET_SB_EXCHANGE_CONTRACT_ADDRESS') is not None:
        IBET_SB_EXCHANGE_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('IBET_SB_EXCHANGE_CONTRACT_ADDRESS'))

    # IbetCouponExchange-Contract
    IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = ''
    if os.environ.get('IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS') is not None:
        IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS'))

    # IbetMembershipExchange-Contract
    IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = ''
    if os.environ.get('IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS') is not None:
        IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS'))

    # IbetShareExchange-Contract
    IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS = ''
    if os.environ.get('IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS') is not None:
        IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS = \
            to_checksum_address(os.environ.get('IBET_SHARE_EXCHANGE_CONTRACT_ADDRESS'))

    # Payment Agent Address
    AGENT_ADDRESS = ''
    if os.environ.get('AGENT_ADDRESS') is not None:
        AGENT_ADDRESS = to_checksum_address(os.environ.get('AGENT_ADDRESS'))

    # RSA鍵ファイルのパスワード
    RSA_PASSWORD = os.environ.get('RSA_PASSWORD')

    # 売出価格（単価）の上限値（円）
    MAX_SELL_PRICE = os.environ.get('MAX_SELL_PRICE') or 100000000

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
