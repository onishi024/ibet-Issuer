"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""
import os
import sys
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Token Template ID
    TEMPLATE_ID_SB = 1  # BOND
    TEMPLATE_ID_COUPON = 2  # COUPON
    TEMPLATE_ID_MEMBERSHIP = 3  # MEMBERSHIP
    TEMPLATE_ID_SHARE = 4  # SHARE

    # Gunicorn Worker Count
    WORKER_COUNT = int(os.environ.get("WORKER_COUNT")) if os.environ.get("WORKER_COUNT") else 4

    # App Env
    APP_ENV = os.getenv("FLASK_CONFIG") or "default"

    # Company List
    COMPANY_LIST_URL = {}
    if APP_ENV == "production":
        COMPANY_LIST_URL["IBET"] = "https://s3-ap-northeast-1.amazonaws.com/ibet-company-list/company_list.json"
        COMPANY_LIST_URL["IBETFIN"] = "https://s3-ap-northeast-1.amazonaws.com/ibet-fin-company-list/company_list.json"
    else:
        COMPANY_LIST_URL["IBET"] = "https://s3-ap-northeast-1.amazonaws.com/ibet-company-list-dev/company_list.json"
        COMPANY_LIST_URL["IBETFIN"] = "https://s3-ap-northeast-1.amazonaws.com/ibet-fin-company-list-dev/company_list.json"

    # SSL
    SECRET_KEY = os.environ.get("SECRET_KEY") or "ZwiTDW52gQlxBQ8Sn34KYaLNQxA0mvpT2_RjYH5j-ZU="
    SSL_DISABLE = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # JWT (JSON Web Token)
    JWT_AUTH_URL_RULE = "/api/auth"
    JWT_AUTH_USERNAME_KEY = "login_id"

    # Database / SQL Alchemy
    SQLALCHEMY_DATABASE_URI = \
        os.environ.get("DATABASE_URL") or "postgresql://issueruser:issuerpass@localhost:5432/issuerdb"
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True

    # Navigation Menu
    NAVI_MENU = {
        "admin": [
            ("account", "glyphicon glyphicon-user", "アカウント管理", [
                ("account_list", "fa fa-list", "アカウント一覧", "account.list"),
                ("account_regist", "fa fa-user-plus", "アカウント追加", "account.regist"),
            ]),
        ]
    }
    NAVI_MENU_USER = [
        ("share", "glyphicon glyphicon-th", "SHARE", [
            ("share_issue", "fa fa-circle-o", "新規発行", "share.issue"),
            ("share_list", "fa fa-circle-o", "発行済一覧", "share.list"),
            ("share_bulk_transfer", "fa fa-circle-o", "一括強制移転", "share.bulk_transfer")
        ]),
        ("bond", "glyphicon glyphicon-th", "BOND", [
            ("bond_issue", "fa fa-circle-o", "新規発行", "bond.issue"),
            ("bond_list", "fa fa-circle-o", "発行済一覧", "bond.list"),
            ("bond_position", "fa fa-circle-o", "売出管理", "bond.positions"),
            ("bond_bulk_transfer", "fa fa-circle-o", "一括強制移転", "bond.bulk_transfer")
        ]),
        ("membership", "glyphicon glyphicon-th", "MEMBERSHIP", [
            ("membership_issue", "fa fa-circle-o", "新規発行", "membership.issue"),
            ("membership_list", "fa fa-circle-o", "発行済一覧", "membership.list"),
            ("membership_position", "fa fa-circle-o", "売出管理", "membership.positions"),
            ("membership_bulk_transfer", "fa fa-circle-o", "一括強制移転", "membership.bulk_transfer")
        ]),
        ("coupon", "glyphicon glyphicon-th", "COUPON", [
            ("coupon_issue", "fa fa-circle-o", "新規発行", "coupon.issue"),
            ("coupon_list", "fa fa-circle-o", "発行済一覧", "coupon.list"),
            ("coupon_position", "fa fa-circle-o", "売出管理", "coupon.positions"),
            ("coupon_transfer", "fa fa-circle-o", "個別割当", "coupon.transfer"),
            ("coupon_bulk_transfer", "fa fa-circle-o", "一括強制移転", "coupon.bulk_transfer")
        ]),
    ]
    NAVI_MENU_ADMIN = [
        ("account", "glyphicon glyphicon-cog", "Settings", [
            ("account_list", "fa fa-circle-o", "アカウント管理", "account.list"),
            ("account_bank_info", "fa fa-circle-o", "銀行口座情報", "account.bankinfo"),
            ("account_issuer_info", "fa fa-circle-o", "発行体情報", "account.issuerinfo"),
        ]),
    ]

    # Logging
    LOG_CONFIG = ({
        "version": 1,
        "formatters": {"default": {
            "format": "WEBAPL [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s [in %(pathname)s:%(lineno)d]",
        }},
        "handlers": {"console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "default"
        }},
        "loggers": {
            "api": {
                "handlers": ["console", ],
                "propagate": False,
            }},
        "root": {
            "level": "DEBUG",
        }
    })

    # Web3
    WEB3_HTTP_PROVIDER = os.environ.get("WEB3_HTTP_PROVIDER") or "http://localhost:8545"

    # Transaction Gas Limit
    TX_GAS_LIMIT = int(os.environ.get("TX_GAS_LIMIT")) if os.environ.get("TX_GAS_LIMIT") else 6000000

    # Issuer Secure Parameter Encryption Key
    SECURE_PARAMETER_ENCRYPTION_KEY = os.environ.get("SECURE_PARAMETER_ENCRYPTION_KEY")

    # Private Key Store for AWS Secrets Manager
    AWS_REGION_NAME = "ap-northeast-1"  # NOTE: Currently set to fixed
    AWS_SECRET_ID = os.environ.get("AWS_SECRET_ID")

    # RSA Key File Password
    RSA_PASSWORD = os.environ.get("RSA_PASSWORD")

    # Zero Address
    ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

    # Batch Processing Interval
    INTERVAL_INDEXER_AGREEMENT = int(os.environ.get("INTERVAL_INDEXER_AGREEMENT")) \
        if os.environ.get("INTERVAL_INDEXER_AGREEMENT") else 1
    INTERVAL_INDEXER_APPLY_FOR = int(os.environ.get("INTERVAL_INDEXER_APPLY_FOR")) \
        if os.environ.get("INTERVAL_INDEXER_APPLY_FOR") else 60
    INTERVAL_INDEXER_CONSUME = int(os.environ.get("INTERVAL_INDEXER_CONSUME")) \
        if os.environ.get("INTERVAL_INDEXER_CONSUME") else 60
    INTERVAL_INDEXER_ORDER = int(os.environ.get("INTERVAL_INDEXER_ORDER")) \
        if os.environ.get("INTERVAL_INDEXER_ORDER") else 1
    INTERVAL_INDEXER_PERSONAL_INFO = int(os.environ.get("INTERVAL_INDEXER_PERSONAL_INFO")) \
        if os.environ.get("INTERVAL_INDEXER_PERSONAL_INFO") else 10
    INTERVAL_INDEXER_TRANSFER = int(os.environ.get("INTERVAL_INDEXER_TRANSFER")) \
        if os.environ.get("INTERVAL_INDEXER_TRANSFER") else 1
    INTERVAL_INDEXER_TRANSFER_APPROVAL = int(os.environ.get("INTERVAL_INDEXER_TRANSFER_APPROVAL")) \
        if os.environ.get("INTERVAL_INDEXER_TRANSFER_APPROVAL") else 60
    INTERVAL_PROCESSOR_APPROVE_TRANSFER = int(os.environ.get("INTERVAL_PROCESSOR_APPROVE_TRANSFER")) \
        if os.environ.get("INTERVAL_PROCESSOR_APPROVE_TRANSFER") else 60
    INTERVAL_PROCESSOR_BATCH_TRANSFER = int(os.environ.get("INTERVAL_PROCESSOR_BATCH_TRANSFER")) \
        if os.environ.get("INTERVAL_PROCESSOR_BATCH_TRANSFER") else 10
    INTERVAL_PROCESSOR_BOND_LEDGER_JP = int(os.environ.get("INTERVAL_PROCESSOR_BOND_LEDGER_JP")) \
        if os.environ.get("INTERVAL_PROCESSOR_BOND_LEDGER_JP") else 60
    INTERVAL_PROCESSOR_ISSUE_EVENT = int(os.environ.get("INTERVAL_PROCESSOR_ISSUE_EVENT")) \
        if os.environ.get("INTERVAL_PROCESSOR_ISSUE_EVENT") else 10

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    LOGIN_DISABLED = True
    SQLALCHEMY_DATABASE_URI = \
        os.environ.get("TEST_DATABASE_URL") or "postgresql://issueruser:issuerpass@localhost:5432/issuerdb_test"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    LOG_CONFIG = ({
        "version": 1,
        "formatters": {"default": {
            "format": "WEBAPL [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s",
        }},
        "handlers": {"console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "default"
        }},
        "loggers": {
            "api": {
                "handlers": ["console", ],
                "propagate": False,
            }},
        "root": {
            "level": "INFO",
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
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "unix": UnixConfig,
    "default": DevelopmentConfig
}
