# -*- coding:utf-8 -*-
from flask import Blueprint

jdr = Blueprint('jdr', __name__, url_prefix='/jdr')

from . import views
