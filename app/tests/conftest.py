import pytest
import os

from app import create_app
from app import db as _db
from selenium import webdriver
from flask import url_for

from app.models import Role, User

@pytest.fixture(scope='session')
def app(request):
    print('')
    print('<session-app start>')
    app = create_app('testing')
    ctx = app.app_context()
    ctx.push()
    #req_ctx = app.test_request_context()
    #req_ctx.push()

    def teardown():
        ctx.pop()
        print('<session-app end>')

    request.addfinalizer(teardown)
    return app

@pytest.fixture(scope='session')
def db(request, app):
    print('  <session-db start> %s' % _db)
    _db.app = app
    _db.create_all()

    def teardown():
        _db.drop_all()
        print('  <session-db end>')

    request.addfinalizer(teardown)
    return _db

@pytest.fixture(scope="class")
def account(request, db):
    print('      <class start>')

    roles = ['admin', 'user',]
    for r in roles:
        role = Role.query.filter_by(name=r).first()
        if role is None:
            role = Role(name=r)
        db.session.add(role)
    
    users = [
         {'login_id': 'admin', 'user_name': '管理者', 'email': 'turbou@i.softbank.jp', 'role_id': 1, 'password': 'admin'},
         {'login_id': 'oyoyo', 'user_name': 'およよ', 'email': 'oyoyo@i.softbank.jp', 'role_id': 2, 'password': 'oyoyo'},
    ]
    for u_dict in users:
        user = User.query.filter_by(login_id=u_dict['login_id']).first()
        if user is None:
            user = User()
            for key, value in u_dict.items():
                setattr(user, key, value)
            db.session.add(user)
    db.session.commit()

    def teardown():
        db.session.remove()
        print('      <class end>')

    request.addfinalizer(teardown)

@pytest.fixture(scope='module')
def driver(request):
    # https://github.com/mbithenzomo/flask-selenium-webdriver-part-one/blob/master/tests/test_front_end.py#L98
    chrome_driver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'chromedriver'))
    firefox_driver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'geckodriver'))
    b = webdriver.Chrome(executable_path=chrome_driver_path)
    #b = webdriver.Firefox(executable_path=firefox_driver_path)
    #b.get('http://localhost:5000')

    def teardown():
        b.quit()

    request.addfinalizer(teardown)

    return b

@pytest.fixture
def driver_with_admin_login(request, driver):
    login_link = 'http://localhost:5000' + url_for('auth.login')
    driver.get(login_link)
    driver.find_element_by_id("login_id").send_keys('admin')
    driver.find_element_by_id("password").send_keys('admin')
    driver.find_element_by_id("submit").click()
    return driver

@pytest.fixture
def driver_with_login(request, driver):
    login_link = 'http://localhost:5000' + url_for('auth.login')
    driver.get(login_link)
    driver.find_element_by_id("login_id").send_keys('oyoyo')
    driver.find_element_by_id("password").send_keys('oyoyo')
    driver.find_element_by_id("submit").click()
    return driver

