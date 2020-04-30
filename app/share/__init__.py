# -*- coding:utf-8 -*-
from flask import Blueprint

share = Blueprint('share', __name__, url_prefix='/share')

from . import views
