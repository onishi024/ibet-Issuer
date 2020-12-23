"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

from http import HTTPStatus
from logging import getLogger

from flask import jsonify
from werkzeug.exceptions import InternalServerError

from app.exceptions import ValidationError
from . import api

logger = getLogger('api')


def bad_request(message):
    """
    入力値エラー（400）
    :param message: エラーメッセージ
    :return: HTTPレスポンス
    """
    response = jsonify({
        'description': message,
        'error': 'Bad Request',
        'status_code': 400
    })
    response.status_code = 400
    return response


def unauthorized(message):
    """
    認証エラー（401）
    :param message: エラーメッセージ
    :return: HTTPレスポンス
    """
    response = jsonify({
        'description': message,
        'error': 'Authorization Required',
        'status_code': 401
    })
    response.status_code = 401
    return response


def forbidden(message):
    """
    権限エラー（400）
    :param message: エラーメッセージ
    :return: HTTPレスポンス
    """
    response = jsonify({
        'description': message,
        'error': 'Forbidden',
        'status_code': 403
    })
    response.status_code = 403
    return response


@api.errorhandler(HTTPStatus.NOT_FOUND)
def not_found_error(e):
    """
    未検出エラー（404）を処理する
    :param e: Exception
    :return: HTTPレスポンス
    """
    response = jsonify({
        'error': 'Not Found',
        'status_code': 404
    })
    response.status_code = 404
    return response


@api.errorhandler(InternalServerError)
def internal_server_error(e):
    """
    内部エラー（500）を処理する
    :param e: Exception
    :return: HTTPレスポンス
    """
    # InternalServerErrorの発生原因となったエラーをログに出力する
    original_exception = getattr(e, "original_exception", e)
    logger.error(original_exception)

    response = jsonify({
        'error': 'Internal Server Error',
        'status_code': 500
    })
    response.status_code = 500
    return response


@api.errorhandler(ValidationError)
def validation_error(e):
    """
    バリデーションエラーを処理する
    :param e: Exception
    :return: HTTPレスポンス
    """
    return bad_request(e.args[0])
