import pytest
import os

from flask import url_for

from app import create_app
from app import db as _db
from app.models import *
from config import Config

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
        #_db.drop_all()
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
        },{
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

@pytest.fixture(scope="class")
def account(request, db):
    print('    <class start>')
    #init_login_user(db)

    def teardown():
        #db.session.remove()
        print('    <class end>')

    request.addfinalizer(teardown)

class TestBase(object):
    data = None

    def add_data(self, param_db, table_name, data_rows):
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

    def client_with_user_login(self, param_app):
        client = param_app.test_client()
        client.post(url_for('auth.login'), data={'login_id': 'user', 'password': '1234'})
        return client

    def client_with_admin_login(self, param_app):
        client = param_app.test_client()
        client.post(url_for('auth.login'), data={'login_id': 'admin', 'password': '1234'})
        return client
