#!/usr/local/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import logging
import qrcode

from web3 import Web3

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Tokenテーブルのtemplate_id
    TEMPLATE_ID_SB = 1
    TEMPLATE_ID_COUPON = 2
    TEMPLATE_ID_MEMBERSHIP = 3

    # Payment Agent List
    APP_ENV = os.getenv('FLASK_CONFIG') or 'default'
    if APP_ENV == 'production':
        PAYMENT_AGENT_LIST_URL = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list/payment_agent_list.json'
    else:
        PAYMENT_AGENT_LIST_URL = 'https://s3-ap-northeast-1.amazonaws.com/ibet-company-list-dev/payment_agent_list.json'

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
            ('token_list', 'fa fa-list', '発行済債券一覧', 'token.list'),
            ('token_issue', 'fa fa-plus-square-o', '債券新規発行', 'token.issue'),
            ('token_position', 'fa fa-yen', '債券募集管理', 'token.positions'),
        ]),
        ('membership', 'glyphicon glyphicon-list-alt', '会員権発行管理', [
            ('membership_list', 'fa fa-list', '会員権一覧', 'membership.list'),
            ('membership_issue', 'fa fa-plus-square-o', '会員権新規発行', 'membership.issue'),
            ('membership_position', 'fa fa-yen', '会員権募集管理', 'membership.positions'),
        ]),
        ('coupon', 'glyphicon glyphicon-list-alt', 'クーポン発行管理', [
            ('coupon_list', 'fa fa-list', 'クーポン一覧', 'coupon.list'),
            ('coupon_issue', 'fa fa-plus-square-o', 'クーポン発行', 'coupon.issue'),
            ('coupon_position', 'fa fa-yen', 'クーポン募集管理', 'coupon.positions'),
            ('coupon_transfer', 'fa fa-send', 'クーポン割当', 'coupon.transfer')
        ]),
    ]

    NAVI_MENU_ADMIN = [
        ('account', 'glyphicon glyphicon-user', 'アカウント管理', [
            ('account_list', 'fa fa-list', 'アカウント一覧', 'account.list'),
            ('account_bank_info', 'fa fa-bank', '銀行情報登録', 'account.bankinfo'),
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

    WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'

    web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
    ETH_ACCOUNT = os.environ.get('ETH_ACCOUNT') or web3.eth.accounts[0]
    ETH_ACCOUNT_PASSWORD = os.environ.get('ETH_ACCOUNT_PASSWORD')
    img = qrcode.make(ETH_ACCOUNT)
    img.save('app/static/eth_address.png')

    # TokenList-Contract
    TOKEN_LIST_CONTRACT_ADDRESS = os.environ.get('TOKEN_LIST_CONTRACT_ADDRESS')

    # WhiteList-Contract
    WHITE_LIST_CONTRACT_ADDRESS = os.environ.get('WHITE_LIST_CONTRACT_ADDRESS')

    # PersonalInfo-Contract
    PERSONAL_INFO_CONTRACT_ADDRESS = os.environ.get('PERSONAL_INFO_CONTRACT_ADDRESS')

    # IbetStraightBondExchange-Contract
    IBET_SB_EXCHANGE_CONTRACT_ADDRESS = os.environ.get('IBET_SB_EXCHANGE_CONTRACT_ADDRESS')

    # IbetCouponExchange-Contract
    IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = os.environ.get('IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS')

    # IbetMembershipExchange-Contract
    IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS = os.environ.get('IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS')

    AGENT_ADDRESS = os.environ.get('AGENT_ADDRESS')

    #RSA鍵ファイルのパスワード
    RSA_PASSWORD = os.environ.get('RSA_PASSWORD')

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
    WTF_CSRF_ENABLED = False

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
