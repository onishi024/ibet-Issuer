"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_jwt import JWT
from config import config
from . import errors

from logging import getLogger
logger = getLogger('api')

mail = Mail()
db = SQLAlchemy()

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'
login_manager.login_message = u"ログインが必要です。"
login_manager.login_message_category = "info"


def authenticate(login_id, password):
    from .models import User
    logger.info('api/auth')
    user = User.query.filter_by(login_id=login_id).first()
    if user and user.verify_password(password):
        return user


def identity(payload):
    from .models import User
    user_id = payload['identity']
    return user_id


def create_app(config_name):
    from .app import app
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    mail.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)

    # logging
    from logging import getLogger
    from logging.config import dictConfig
    werkzeug_logger = getLogger('werkzeug')
    werkzeug_logger.disabled = True
    app.logger.handlers.clear()
    dictConfig(app.config['LOG_CONFIG'])

    from .index import index_blueprint
    app.register_blueprint(index_blueprint)

    from .account import account as account_blueprint
    app.register_blueprint(account_blueprint)

    from .bond import bond as token_blueprint
    app.register_blueprint(token_blueprint)

    from .coupon import coupon as coupon_blueprint
    app.register_blueprint(coupon_blueprint)

    from .membership import membership as membership_blueprint
    app.register_blueprint(membership_blueprint)

    from .share import share as share_blueprint
    app.register_blueprint(share_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    JWT(app, authenticate, identity)
    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    from .dashboard import dashboard as dashboard_blueprint
    app.register_blueprint(dashboard_blueprint, url_prefix='/dashboard')

    return app
