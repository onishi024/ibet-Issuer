from flask import render_template, request, jsonify
from .index import index_blueprint
from .app import app

from logging import getLogger

logger = getLogger('api')


@index_blueprint.app_errorhandler(400)
def bad_request(e):
    response = jsonify({'error': 'bad request'})
    response.status_code = 400
    return response

@index_blueprint.app_errorhandler(403)
def forbidden(e):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'forbidden'})
        response.status_code = 403
        return response
    return render_template('403.html'), 403


@index_blueprint.app_errorhandler(404)
def page_not_found(e):
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response
    return render_template('404.html'), 404


@index_blueprint.app_errorhandler(500)
def internal_server_error(e):
    logger.exception(e)
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'internal server error'})
        response.status_code = 500
        return response
    return render_template('500.html'), 500


@app.errorhandler(Exception)
def exception_handler(e):
    logger.exception(e)
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'internal server error'})
        response.status_code = 500
        return response
    return render_template('500.html'), 500
