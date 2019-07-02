#!/usr/local/bin/python
# -*- coding:utf-8 -*-
import os
import sys

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


class user_role_migrate(Command):
    def run(self):
        print ('user_rolo_migrate')
        roles = ['admin','user',]
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            db.session.add(role)
        users = [
     {'login_id': 'admin', 'user_name': '管理者', 'role_id': 1, 'password': 'admin'},
        ]

        for u_dict in users:
            user = User.query.filter_by(login_id=u_dict['login_id']).first()
            if user is None:
                user = User()
                for key, value in u_dict.items():
                    setattr(user, key, value)
                db.session.add(user)

        db.session.commit()


class drop_alnum(Command):
    def run(self):
        print ('drop_alnum')
        #sql = text('DROP TABLE IF EXISTS alembic_version;')
        Alembic_version.__table__.drop(db.engine)


manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)
manager.add_command("user_role_migrate", user_role_migrate())
manager.add_command("drop_alnum", drop_alnum())

import pytest
@manager.option('-v', dest='v_opt', action="store_true", help='pytest -v option add.', default=False, required=False)
@manager.option('-s', dest='s_opt', action="store_true", help='pytest -s option add.', default=False, required=False)
@manager.option('-x', dest='x_opt', action="store_true", help='pytest -x option add.', default=False, required=False)
@manager.option('-m', '--module', dest='module', help='can specify module.', default=None, required=False)
@manager.option('--cov', dest='cov', action="store_true", help='coverage mode on.', default=False, required=False)
@manager.option('--pdb', dest='pdb', action="store_true", help='debug mode on.', default=False, required=False)
def test(v_opt, s_opt, x_opt, module, cov, pdb):
    """ Runs pytest """
    pytest_args = []
    if v_opt:
        pytest_args.append("-v")
    if s_opt:
        pytest_args.append("-s")
    if x_opt:
        pytest_args.append("-x")
    if cov:
        pytest_args.append("--cov")
        pytest_args.append("--cov-report=xml")
        pytest_args.append("--cov-branch")
    if pdb:
        pytest_args.append("--pdb")
    if module is None:
        pytest_args.append("app/tests/")
    else:
        pytest_args.append("app/tests/test_%s.py" % module)

    pytest.main(pytest_args)

if __name__ == '__main__':
    manager.run()
