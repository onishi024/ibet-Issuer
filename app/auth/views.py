# -*- coding:utf-8 -*-
from flask import render_template, redirect, request, url_for, flash, session
from flask_login import login_user, logout_user, login_required

from . import auth
from .forms import LoginForm
from ..models import User
from config import Config


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(error, 'error')


@auth.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if request.method == 'POST' and form.validate() is True:
        user = User.query.filter_by(login_id=form.login_id.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user)
            session['login_id'] = user.login_id
            session['eth_address'] = Config.ETH_ACCOUNT
            return redirect(request.args.get('next') or url_for('index.index'))
        else:
            flash('ログインID又はパスワードが正しくありません。', 'error')
    elif request.method == 'POST' and form.validate() is False:
        flash_errors(form)
        return redirect(url_for('.login'))

    return render_template('login.html', form=form, next_url=request.args.get('next'))


@auth.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index.index'))
