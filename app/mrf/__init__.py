# -*- coding:utf-8 -*-
from flask import Blueprint

mrf = Blueprint('mrf', __name__, url_prefix='/mrf')

from . import views
