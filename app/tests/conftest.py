import json

import pytest
import os

import yaml
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app import create_app
from app import db as _db
from app.models import *
from config import Config
from app.tests.utils.account_config import eth_account
from app.contracts import Contract


# ---------------------------------------------------------------------------------------------
# DB系
# ---------------------------------------------------------------------------------------------
@pytest.fixture(scope='session')
def app(request):
    print('')
    print('<session-app start>')
    app = create_app('testing')
    ctx = app.app_context()
    ctx.push()

    def teardown():
        ctx.pop()
        print('<session-app end>')

    request.addfinalizer(teardown)
    return app


@pytest.fixture(scope='session')
def db(request, app):
    print('  <session-db start> %s' % _db)
    _db.app = app
    _db.drop_all()
    _db.create_all()

    def teardown():
        # _db.drop_all()
        print('  <session-db end>')

    request.addfinalizer(teardown)
    return _db


@pytest.fixture(scope='session')
def init_login_user(db):
    roles = ['admin', 'user']
    for r in roles:
        role = Role.query.filter_by(name=r).first()
        if role is None:
            role = Role(name=r)
            db.session.add(role)

    users = [
        {
            'login_id': 'admin',
            'user_name': '管理者',
            'role_id': 1,
            'password': '1234'
        }, {
            'login_id': 'user',
            'user_name': 'ユーザ',
            'role_id': 2,
            'password': '1234'
        },
    ]

    for u_dict in users:
        user = User()
        for key, value in u_dict.items():
            setattr(user, key, value)
        db.session.add(user)

    db.session.commit()


@pytest.fixture(scope="session", autouse=True)
def db_setup(request, db):
    print('    <class start>')
    init_login_user(db)

    def teardown():
        db.session.remove()
        print('    <class end>')

    request.addfinalizer(teardown)


class TestBase(object):
    data = None

    @staticmethod
    def add_data(param_db, table_name, data_rows):
        for row_no, row_values in data_rows.items():
            cls = globals()[table_name]
            entity = cls()
            for key, value in row_values.items():
                setattr(entity, key, value)
            param_db.session.add(entity)
        param_db.session.commit()

    def db_init_exec(self, param_db, init_ptn=None):
        param_db.session.commit()
        param_db.drop_all()
        param_db.create_all()
        db_init_list = [
            {"table_name": "Role", "start_row": 1, "end_row": 9999},
            {"table_name": "User", "start_row": 1, "end_row": 9999}
        ]
        if self.data is None:
            with open(os.path.abspath(os.path.join(os.path.dirname(__file__), 'data.yaml')), 'r',
                      encoding='utf-8') as s:
                try:
                    self.data = yaml.load(s)
                except yaml.YAMLError as ex:
                    raise ex

        if init_ptn is not None:
            db_init_list.extend(init_ptn)

        for cfg in db_init_list:
            table_name = cfg["table_name"]
            start_row = 'row_%04d' % cfg["start_row"]
            end_row = 'row_%04d' % cfg["end_row"]
            records = self.data[table_name]
            data_rows = {k: v for k, v in records.items() if start_row <= k <= end_row}
            self.add_data(param_db, table_name, data_rows)

    @staticmethod
    def client_with_user_login(param_app):
        client = param_app.test_client()
        client.post(url_for('auth.login'), data={'login_id': 'user', 'password': '1234'})
        return client

    @staticmethod
    def client_with_admin_login(param_app):
        client = param_app.test_client()
        client.post(url_for('auth.login'), data={'login_id': 'admin', 'password': '1234'})
        return client

    @staticmethod
    def client_with_api_login(param_app):
        client = param_app.test_client()
        response = client.post('/api/auth', json={'login_id': 'admin', 'password': '1234'})
        return client, json.loads(response.data.decode('utf-8'))['access_token']

# ---------------------------------------------------------------------------------------------
# quorum系
# ---------------------------------------------------------------------------------------------
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


def payment_gateway_contract():
    deployer = eth_account['deployer']
    agent = eth_account['agent']

    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])
    contract_address, abi, _ = \
        Contract.deploy_contract('PaymentGateway', [], deployer['account_address'])

    contract = Contract.get_contract('PaymentGateway', contract_address)
    tx_hash = contract.functions.addAgent(agent['account_address']).transact(
        {'from': deployer['account_address'], 'gas': 4000000}
    )
    web3.eth.waitForTransactionReceipt(tx_hash)

    return {'address': contract_address, 'abi': abi}


def personalinfo_contract():
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    contract_address, abi, _ = Contract.deploy_contract(
        'PersonalInfo', [], deployer['account_address'])

    return {'address': contract_address, 'abi': abi}


def exchange_regulator_service_contract():
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    contract_address, abi, _ = Contract.deploy_contract('ExchangeRegulatorService', [], deployer['account_address'])

    exchange_regulator_service = Contract.get_contract('ExchangeRegulatorService', contract_address)
    web3.eth.defaultAccount = deployer['account_address']
    exchange_regulator_service.functions.register(eth_account['issuer']['account_address'], False).\
        transact({'from': deployer['account_address'], 'gas': 4000000})
    exchange_regulator_service.functions.register(eth_account['trader']['account_address'], False).\
        transact({'from': deployer['account_address'], 'gas': 4000000})

    return {'address': contract_address, 'abi': abi}


def tokenlist_contract():
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    contract_address, abi, _ = Contract.deploy_contract(
        'TokenList', [], deployer['account_address'])

    return {'address': contract_address, 'abi': abi}


# Straight Bond Exchange
def bond_exchange_contract(payment_gateway_address, personalinfo_address, exchange_regulator_service_address):
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    issuer = eth_account['issuer']
    web3.eth.defaultAccount = issuer['account_address']
    web3.personal.unlockAccount(issuer['account_address'], issuer['password'])

    trader = eth_account['trader']
    web3.eth.defaultAccount = trader['account_address']
    web3.personal.unlockAccount(trader['account_address'], trader['password'])

    storage_address, _, _ = Contract.deploy_contract('ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        personalinfo_address,
        storage_address,
        exchange_regulator_service_address
    ]

    contract_address, abi, _ = Contract.deploy_contract(
        'IbetStraightBondExchange', args, deployer['account_address'])

    storage = Contract.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': 4000000}
    )

    # 取引参加者登録
    ExchangeRegulatorService = \
        Contract.get_contract('ExchangeRegulatorService', exchange_regulator_service_address)
    ExchangeRegulatorService.functions.register(issuer['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': 4000000})
    ExchangeRegulatorService.functions.register(trader['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': 4000000})

    return {'address': contract_address, 'abi': abi}


# Coupon Exchange
def coupon_exchange_contract(payment_gateway_address):
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    storage_address, _, _ = Contract.deploy_contract(
        'ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        storage_address
    ]

    contract_address, abi, _ = Contract.deploy_contract(
        'IbetCouponExchange', args, deployer['account_address'])

    storage = Contract.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': 4000000}
    )

    return {'address': contract_address, 'abi': abi}


# Membership Exchange
def membership_exchange_contract(payment_gateway_address):
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    storage_address, _, _ = Contract.deploy_contract(
        'ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        storage_address
    ]

    contract_address, abi, _ = Contract.deploy_contract(
        'IbetMembershipExchange', args, deployer['account_address'])

    storage = Contract.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': 4000000}
    )

    return {'address': contract_address, 'abi': abi}


# OTC Exchange
def otc_exchange_contract(payment_gateway_address, personalinfo_address, exchange_regulator_service_address):
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    issuer = eth_account['issuer']
    web3.eth.defaultAccount = issuer['account_address']
    web3.personal.unlockAccount(issuer['account_address'], issuer['password'])

    trader = eth_account['trader']
    web3.eth.defaultAccount = trader['account_address']
    web3.personal.unlockAccount(trader['account_address'], trader['password'])

    storage_address, _, _ = Contract.deploy_contract('ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        personalinfo_address,
        storage_address,
        exchange_regulator_service_address
    ]

    contract_address, abi, _ = Contract.deploy_contract(
        'IbetOTCExchange', args, deployer['account_address'])

    storage = Contract.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': 4000000}
    )

    # 取引参加者登録
    ExchangeRegulatorService = \
        Contract.get_contract('ExchangeRegulatorService', exchange_regulator_service_address)
    ExchangeRegulatorService.functions.register(issuer['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': 4000000})
    ExchangeRegulatorService.functions.register(trader['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': 4000000})

    return {'address': contract_address, 'abi': abi}


@pytest.fixture(scope='class')
def shared_contract():
    payment_gateway = payment_gateway_contract()
    personal_info = personalinfo_contract()
    exchange_regulator_service = exchange_regulator_service_contract()
    bond_exchange = bond_exchange_contract(
        payment_gateway['address'],
        personal_info['address'],
        exchange_regulator_service['address']
    )
    membership_exchange = membership_exchange_contract(payment_gateway['address'])
    token_list = tokenlist_contract()
    coupon_exchange = coupon_exchange_contract(payment_gateway['address'])
    otc_exchange = otc_exchange_contract(
        payment_gateway['address'],
        personal_info['address'],
        exchange_regulator_service['address']
    )
    contracts = {
        'PaymentGateway': payment_gateway,
        'PersonalInfo': personal_info,
        'IbetStraightBondExchange': bond_exchange,
        'TokenList': token_list,
        'IbetCouponExchange': coupon_exchange,
        'IbetMembershipExchange': membership_exchange,
        'IbetShareExchange': otc_exchange
    }
    return contracts
