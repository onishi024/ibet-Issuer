#!/usr/local/bin/python
# -*- coding:utf-8 -*-
import os

if os.path.exists('.env'):
    print('Importing environment from .env...')
    for line in open('.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1]

from app import create_app, db
from app.models import User, Role
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)

def make_shell_context():
    return dict(
            app = app, db = db,
            User = User,
            Role = Role,
        )

manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

import pytest
@manager.option('-s', dest='s_opt', action="store_true", help='pytest -s option add.', default=False, required=False)
@manager.option('-m', '--module', dest='module', help='can specify module.', default=None, required=False)
@manager.option('--cov', dest='cov', action="store_true", help='coverage mode on.', default=False, required=False)
def test(s_opt, module, cov):
    """ Runs pytest """
    pytest_args = []
    if s_opt:
        pytest_args.append("-s")
    if cov:
        pytest_args.append("--cov")
        pytest_args.append("--cov-report=html")
    if module is None:
        pytest_args.append("app/tests/")
    else:
        pytest_args.append("app/tests/test_%s.py" % module)
    pytest.main(pytest_args)

if __name__ == '__main__':
    manager.run()