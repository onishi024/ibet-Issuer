# -*- coding:utf-8 -*-
from flask import Blueprint

token = Blueprint('token', __name__, url_prefix='/token')

from . import views
