# -*- coding:utf-8 -*-
from functools import wraps
from flask_login import current_user
from flask import abort
from flask_login import AnonymousUserMixin

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous:
            return f(*args, **kwargs)
        if current_user.role.name != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

