# -*- coding:utf-8 -*-
from flask import Blueprint, render_template
from flask_login import login_required

from logging import getLogger
logger = getLogger('api')

index_blueprint = Blueprint('index', __name__)

@index_blueprint.route('/', methods=['GET'])
@login_required
def index():
    return render_template('main.html')
