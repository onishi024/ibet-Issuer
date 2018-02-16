# -*- coding:utf-8 -*-
from datetime import datetime as dt
from flask import Blueprint, redirect, url_for, render_template
from flask_login import login_required
from sqlalchemy import and_

from logging import getLogger
logger = getLogger('api')

index_blueprint = Blueprint('index', __name__)

@index_blueprint.route('/', methods=['GET'])
@login_required
def index():
    return render_template('main.html')
