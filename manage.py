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

import difflib
import getpass
import os
import re
import secrets
import string
import sys
from collections import OrderedDict
from Crypto.PublicKey import RSA
from Crypto import Random

import yaml
from cryptography.fernet import Fernet
from eth_utils import to_checksum_address
from web3 import Web3

from app import create_app, db
from app.models import AlembicVersion, User, Role, Issuer
from flask_script import Manager, Shell, Command
from flask_migrate import Migrate, MigrateCommand

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)


###############################################
# 対話シェル
###############################################
def make_shell_context():
    return {'app': app, 'db': db, 'User': User, 'Role': Role}


manager.add_command("shell", Shell(make_context=make_shell_context))

###############################################
# DBマイグレーション
###############################################
migrate = Migrate(app, db, compare_type=True)
manager.add_command("db", MigrateCommand)


###############################################
# DBリセット（AlembicVersionテーブルの削除）
###############################################
class DropAlembicVersion(Command):
    def run(self):
        AlembicVersion.__table__.drop(db.engine)


manager.add_command("resetdb", DropAlembicVersion())


###############################################
# ログインユーザ・ロールの作成
###############################################
@manager.command
def create_user(login_id, eth_account):
    """初期ログインユーザの作成

    :param login_id: ログインID
    :param eth_account: 発行体のアカウントアドレス
    :return: なし
    """

    # login_id 設定可能文字種チェック
    # 設定可能文字種：半角英数字およびアンダースコア
    alnum_Reg = re.compile(r"^[a-zA-Z0-9_]+$")
    if alnum_Reg.match(login_id) is not None:
        pass
    else:
        print("ERROR: Only alphanumeric characters and underscores are allowed for login_id.")
        return

    # ロールの作成
    # 既存のデータが存在しない場合にのみレコードを作成する
    roles = ["admin", "user"]
    for r in roles:
        role = Role.query.filter_by(name=r).first()
        if role is None:
            role = Role(name=r)
        db.session.add(role)

    # 初期パスワード生成（12桁）
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    init_password = ''.join(secrets.choice(chars) for x in range(12))

    # ログインユーザ（管理者権限）の作成
    users = [
        {
            "eth_account": eth_account,
            "login_id": login_id,
            "user_name": "管理者",
            "role_id": 1,
            "password": init_password
        },
    ]
    for u_dict in users:
        user = User.query.filter_by(login_id=u_dict['login_id']).first()
        if user is None:
            user = User()
            for key, value in u_dict.items():
                setattr(user, key, value)
            db.session.add(user)
        else:
            print("ERROR: login_id is already used.")
            db.session.rollback()
            return

    db.session.commit()
    print("Successfully created.")
    print(f"Initial password = {init_password}")


###############################################
# RSA鍵の作成
###############################################
@manager.command
def create_rsakey(pass_phrase):
    """RSA鍵ファイルの作成

    - private key file: data/rsa/private.pem
    - public key file: data/rsa/public.pem
    """
    random_func = Random.new().read
    rsa = RSA.generate(10240, random_func)

    # 秘密鍵作成
    private_pem = rsa.exportKey(format='PEM', passphrase=pass_phrase)
    with open('data/rsa/private.pem', 'wb') as f:
        f.write(private_pem)

    # 公開鍵作成
    public_pem = rsa.publickey().exportKey()
    with open('data/rsa/public.pem', 'wb') as f:
        f.write(public_pem)


###############################################
# セキュアパラメータ暗号化鍵の作成
###############################################
@manager.command
def create_enckey():
    """セキュアパラメータ暗号化鍵の作成

    - セキュアパレメータ暗号化鍵はDBに保存される発行体のセキュアパラメータを暗号化・復号化するために利用される
    """
    secret_key = Fernet.generate_key().decode()
    print(f'SECURE_PARAMETER_ENCRYPTION_KEY="{secret_key}"')


###############################################
# 発行体設定
###############################################
def _represent_odict(dumper, instance):
    return dumper.represent_mapping('tag:yaml.org,2002:map', instance.items())


yaml.add_representer(OrderedDict, _represent_odict)


def _issuer_to_text(issuer):
    data = OrderedDict()
    for column in vars(Issuer):
        if column.startswith('_') or column == 'id':
            continue
        if column.startswith('encrypted_'):
            continue
        data[column] = issuer[column]
    return yaml.dump(data, default_flow_style=False, allow_unicode=True)


@manager.command
def issuer_template():
    """Shows issuer information with default values"""
    default_values = {}
    for column in vars(Issuer):
        if column.startswith('_') or column == 'id':
            continue
        if column.startswith('encrypted_'):
            continue
        default = Issuer.__table__.columns[column].default
        default_values[column] = default.arg if default is not None else ''
    print(_issuer_to_text(default_values))


@manager.option('eth_account', help='issuer address')
def issuer_show(eth_account):
    """Shows issuer information"""
    issuer = Issuer.query.filter(Issuer.eth_account == eth_account).first()
    if issuer is None:
        print(f'ERROR: Issuer {eth_account} was not found', file=sys.stderr)
        return
    print(_issuer_to_text(issuer.__dict__))


@manager.option(
    'issuer_file',
    help='issuer information file, which can be create by `issuer_template` or `issuer_show`'
)
@manager.option(
    '--rsa-privatekey',
    help='specify RSA private key file',
    required=False
)
@manager.option(
    '--eoa-keyfile-password',
    action="store_true",
    help='update EOA keyfile password',
    default=False,
    required=False
)
def issuer_save(issuer_file, rsa_privatekey, eoa_keyfile_password):
    """Creates or updates issuer information"""

    ADDRESS_COLUMNS = [
        re.compile('eth_account'),
        re.compile('agent_address'),
        re.compile('.*_contract_address$')
    ]

    # parse issuer_file
    with open(issuer_file) as f:
        new_values = yaml.load(f)
    for key, value in new_values.items():
        for pattern in ADDRESS_COLUMNS:
            if value and pattern.match(key) and not Web3.isChecksumAddress(value):
                print(f'{key} is not a checksum address')
                return

    # load current issuer
    eth_account = to_checksum_address(new_values['eth_account'])
    current_issuer = Issuer.query.filter(Issuer.eth_account == eth_account).first()

    # EOA keyfile password
    encrypted_eoa_keyfile_password = None
    if eoa_keyfile_password:
        print(f'Input the EOA keyfile password for {eth_account}')
        password = getpass.getpass()
        fernet = Fernet(os.environ['SECURE_PARAMETER_ENCRYPTION_KEY'])
        encrypted_eoa_keyfile_password = fernet.encrypt(password.encode()).decode()

    # RSA private key
    # NOTE: RSA鍵ファイルはデフォルトで暗号化されているのでそのままDBに保存する
    rsa_privatekey_file = None
    if rsa_privatekey is not None:
        with open(rsa_privatekey) as f:
            rsa_privatekey_file = f.read()

    # user confirmation of changes
    print('\nChanges:')
    if encrypted_eoa_keyfile_password is not None:
        print('EOA keyfile password will be updated.')
    if rsa_privatekey_file is not None:
        print('RSA private key will be updated.')

    if current_issuer is None:
        print(_issuer_to_text(new_values))
        prompt = input('Do you really want to create? [yes/[no]] ')
        if prompt.lower() != 'yes':
            print('aborted.')
            return

        issuer = Issuer()
        for key, value in new_values.items():
            setattr(issuer, key, value)
        if encrypted_eoa_keyfile_password is not None:
            issuer.encrypted_account_password = encrypted_eoa_keyfile_password
        if rsa_privatekey_file is not None:
            issuer.encrypted_rsa_private_key = rsa_privatekey_file
        db.session.add(issuer)

    else:
        diffs = difflib.ndiff(
            _issuer_to_text(current_issuer.__dict__).splitlines(True),
            _issuer_to_text(new_values).splitlines(True)
        )
        for x in diffs:
            print(x, end='')
        print('')
        prompt = input('Do you really want to update? [yes/[no]] ')
        if prompt.lower() != 'yes':
            print('aborted.')
            return

        for key, value in new_values.items():
            setattr(current_issuer, key, value)
        if encrypted_eoa_keyfile_password is not None:
            current_issuer.encrypted_account_password = encrypted_eoa_keyfile_password
        if rsa_privatekey_file is not None:
            current_issuer.encrypted_rsa_private_key = rsa_privatekey_file

    db.session.commit()
    print("Successfully updated.")


###############################################
# テスト実行
###############################################
@manager.option('-v', dest='v_opt', action="store_true", help='pytest -v option add.', default=False, required=False)
@manager.option('-s', dest='s_opt', action="store_true", help='pytest -s option add.', default=False, required=False)
@manager.option('-x', dest='x_opt', action="store_true", help='pytest -x option add.', default=False, required=False)
@manager.option('-m', '--module', dest='module', help='can specify module.', default=None, required=False)
@manager.option('--cov', dest='cov', action="store_true", help='coverage mode on.', default=False, required=False)
@manager.option('--pdb', dest='pdb', action="store_true", help='debug mode on.', default=False, required=False)
def test(v_opt, s_opt, x_opt, module, cov, pdb):
    import pytest

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
