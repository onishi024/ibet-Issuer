import json

import pytest

from cryptography.fernet import Fernet
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app import create_app
from app import db as _db
from app.models import *
from config import Config
from app.tests.utils.account_config import eth_account
from app.utils import ContractUtils


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
            'password': '1234',
            'eth_account': eth_account['issuer']['account_address']
        }, {
            'login_id': 'user',
            'user_name': 'ユーザ',
            'role_id': 2,
            'password': '1234',
            'eth_account': eth_account['issuer']['account_address']
        },
    ]

    for u_dict in users:
        user = User()
        for key, value in u_dict.items():
            setattr(user, key, value)
        db.session.add(user)

    db.session.commit()


@pytest.fixture(scope='session')
def issuer(db):
    issuer = Issuer.query.filter(Issuer.eth_account == eth_account['issuer']['account_address']).first()
    if issuer is not None:
        return issuer

    fernet = Fernet(Config.SECURE_PARAMETER_ENCRYPTION_KEY)
    encrypted_account_password = fernet.encrypt(eth_account['issuer']['password'].encode()).decode()
    with open('data/rsa/private.pem') as f:
        encrypted_rsa_private_key = f.read()

    issuer = Issuer(
        eth_account=eth_account['issuer']['account_address'],
        issuer_name='発行体１',
        private_keystore='GETH',
        network='IBET',
        max_sell_price=100000000,
        agent_address=eth_account['agent']['account_address'],
        payment_gateway_contract_address='',
        personal_info_contract_address='',
        token_list_contract_address='',
        ibet_share_exchange_contract_address='',
        ibet_sb_exchange_contract_address='',
        ibet_membership_exchange_contract_address='',
        ibet_coupon_exchange_contract_address='',
        encrypted_account_password=encrypted_account_password,
        encrypted_rsa_private_key=encrypted_rsa_private_key,
    )

    db.session.add(issuer)
    db.session.commit()

    return issuer


@pytest.fixture(scope='session')
def issuer2(db):
    issuer2 = Issuer.query.filter(Issuer.eth_account == eth_account['issuer2']['account_address']).first()
    if issuer2 is not None:
        return issuer2

    fernet = Fernet(Config.SECURE_PARAMETER_ENCRYPTION_KEY)
    encrypted_account_password = fernet.encrypt(eth_account['issuer2']['password'].encode()).decode()
    with open('data/rsa/private.pem') as f:
        encrypted_rsa_private_key = f.read()

    deployer = Issuer(
        eth_account=eth_account['issuer2']['account_address'],
        issuer_name='issuer2',
        private_keystore='GETH',
        network='IBET',
        max_sell_price=100000000,
        agent_address=eth_account['agent']['account_address'],
        payment_gateway_contract_address='',
        personal_info_contract_address='',
        token_list_contract_address='',
        ibet_share_exchange_contract_address='',
        ibet_sb_exchange_contract_address='',
        ibet_membership_exchange_contract_address='',
        ibet_coupon_exchange_contract_address='',
        encrypted_account_password=encrypted_account_password,
        encrypted_rsa_private_key=encrypted_rsa_private_key,
    )
    db.session.add(deployer)

    # 発行体2のユーザ
    user = User()
    user.login_id = 'admin2',
    user.user_name = '管理者2',
    user.role_id = 1,
    user.eth_account = eth_account['issuer2']['account_address']
    user.password = '1234'
    db.session.add(user)

    db.session.commit()
    return deployer


@pytest.fixture(scope="session", autouse=True)
def db_setup(request, db):
    print('    <class start>')
    init_login_user(db)
    issuer(db)
    issuer2(db)

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

    @staticmethod
    def client_with_user_login(param_app):
        client = param_app.test_client()
        client.post(url_for('auth.login'), data={'login_id': 'user', 'password': '1234'})
        return client

    @staticmethod
    def client_with_admin_login(param_app, login_id='admin'):
        client = param_app.test_client()
        client.post(url_for('auth.login'), data={'login_id': login_id, 'password': '1234'})
        return client

    @staticmethod
    def client_with_api_login(param_app, login_id="admin"):
        client = param_app.test_client()
        response = client.post('/api/auth', json={'login_id': login_id, 'password': '1234'})
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
        ContractUtils.deploy_contract('PaymentGateway', [], deployer['account_address'])

    print(contract_address)
    contract = ContractUtils.get_contract('PaymentGateway', contract_address)
    tx_hash = contract.functions.addAgent(agent['account_address']).transact(
        {'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT}
    )
    web3.eth.waitForTransactionReceipt(tx_hash)

    return {'address': contract_address, 'abi': abi}


def personalinfo_contract():
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    contract_address, abi, _ = ContractUtils.deploy_contract(
        'PersonalInfo', [], deployer['account_address'])

    return {'address': contract_address, 'abi': abi}


def exchange_regulator_service_contract():
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    contract_address, abi, _ = ContractUtils.deploy_contract('ExchangeRegulatorService', [], deployer['account_address'])

    exchange_regulator_service = ContractUtils.get_contract('ExchangeRegulatorService', contract_address)
    web3.eth.defaultAccount = deployer['account_address']
    exchange_regulator_service.functions.register(eth_account['issuer']['account_address'], False).\
        transact({'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT})
    exchange_regulator_service.functions.register(eth_account['trader']['account_address'], False).\
        transact({'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT})

    return {'address': contract_address, 'abi': abi}


def tokenlist_contract():
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    contract_address, abi, _ = ContractUtils.deploy_contract(
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

    storage_address, _, _ = ContractUtils.deploy_contract('ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        personalinfo_address,
        storage_address,
        exchange_regulator_service_address
    ]

    contract_address, abi, _ = ContractUtils.deploy_contract(
        'IbetStraightBondExchange', args, deployer['account_address'])

    storage = ContractUtils.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT}
    )

    # 取引参加者登録
    ExchangeRegulatorService = \
        ContractUtils.get_contract('ExchangeRegulatorService', exchange_regulator_service_address)
    ExchangeRegulatorService.functions.register(issuer['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT})
    ExchangeRegulatorService.functions.register(trader['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT})

    return {'address': contract_address, 'abi': abi}


# Coupon Exchange
def coupon_exchange_contract(payment_gateway_address):
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    storage_address, _, _ = ContractUtils.deploy_contract(
        'ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        storage_address
    ]

    contract_address, abi, _ = ContractUtils.deploy_contract(
        'IbetCouponExchange', args, deployer['account_address'])

    storage = ContractUtils.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT}
    )

    return {'address': contract_address, 'abi': abi}


# Membership Exchange
def membership_exchange_contract(payment_gateway_address):
    deployer = eth_account['deployer']
    web3.eth.defaultAccount = deployer['account_address']
    web3.personal.unlockAccount(deployer['account_address'], deployer['password'])

    storage_address, _, _ = ContractUtils.deploy_contract(
        'ExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        storage_address
    ]

    contract_address, abi, _ = ContractUtils.deploy_contract(
        'IbetMembershipExchange', args, deployer['account_address'])

    storage = ContractUtils.get_contract('ExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT}
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

    storage_address, _, _ = ContractUtils.deploy_contract('OTCExchangeStorage', [], deployer['account_address'])

    args = [
        payment_gateway_address,
        personalinfo_address,
        storage_address,
        exchange_regulator_service_address
    ]

    contract_address, abi, _ = ContractUtils.deploy_contract(
        'IbetOTCExchange', args, deployer['account_address'])

    storage = ContractUtils.get_contract('OTCExchangeStorage', storage_address)
    storage.functions.upgradeVersion(contract_address).transact(
        {'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT}
    )

    # 取引参加者登録
    ExchangeRegulatorService = \
        ContractUtils.get_contract('ExchangeRegulatorService', exchange_regulator_service_address)
    ExchangeRegulatorService.functions.register(issuer['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT})
    ExchangeRegulatorService.functions.register(trader['account_address'], False). \
        transact({'from': deployer['account_address'], 'gas': Config.TX_GAS_LIMIT})

    return {'address': contract_address, 'abi': abi}


@pytest.fixture(scope='class', autouse=True)
def shared_contract(db, issuer: Issuer):
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

    issuer.payment_gateway_contract_address = payment_gateway['address']
    issuer.personal_info_contract_address = personal_info['address']
    issuer.token_list_contract_address = token_list['address']
    issuer.ibet_sb_exchange_contract_address = bond_exchange['address']
    issuer.ibet_coupon_exchange_contract_address = coupon_exchange['address']
    issuer.ibet_membership_exchange_contract_address = membership_exchange['address']
    issuer.ibet_share_exchange_contract_address = otc_exchange['address']
    db.session.commit()

    return contracts
