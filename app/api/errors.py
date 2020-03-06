from flask import jsonify
from app.exceptions import ValidationError
from . import api
from logging import getLogger
logger = getLogger('api')


def bad_request(message):
    response = jsonify({
        'description': message,
        'error': 'Bad Request',
        'status_code': 400
    })
    response.status_code = 400
    return response


def unauthorized(message):
    response = jsonify({
        'description': message,
        'error': 'Authorization Required',
        'status_code': 401
    })
    response.status_code = 401
    return response


def forbidden(message):
    response = jsonify({
        'description': message,
        'error': 'Forbidden',
        'status_code': 403
    })
    response.status_code = 403
    return response


def internal_server_error():
    response = jsonify({
        'error': 'Internal Server Error',
        'status_code': 500
    })
    response.status_code = 500
    return response


@api.errorhandler(ValidationError)
def validation_error(e):
    return bad_request(e.args[0])
