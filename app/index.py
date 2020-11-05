"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

from flask import Blueprint, redirect, url_for
from flask_login import login_required

from logging import getLogger
logger = getLogger('api')

index_blueprint = Blueprint('index', __name__)


@index_blueprint.route('/', methods=['GET'])
@login_required
def index():
    return redirect(url_for('dashboard.main'))
