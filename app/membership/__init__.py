# -*- coding:utf-8 -*-
from flask import Blueprint

membership = Blueprint('membership', __name__, url_prefix='/membership')

from . import views
