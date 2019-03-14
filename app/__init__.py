# -*- coding:utf-8 -*-
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config
from . import errors

mail = Mail()
db = SQLAlchemy()

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'
login_manager.login_message = u"ログインが必要です。"
login_manager.login_message_category = "info"

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
    #app.logger.disabled = True
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

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    return app
