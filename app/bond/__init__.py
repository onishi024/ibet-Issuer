# -*- coding:utf-8 -*-
from flask import Blueprint

bond = Blueprint('bond', __name__, url_prefix='/bond')

from . import views
