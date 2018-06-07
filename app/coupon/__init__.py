# -*- coding:utf-8 -*-
from flask import Blueprint

coupon = Blueprint('coupon', __name__, url_prefix='/coupon')

from . import views
