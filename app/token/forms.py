# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, PasswordField, SubmitField, HiddenField, SelectField, PasswordField, FileField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from ..models import Role, User
from sqlalchemy import or_, and_

class IssueTokenForm(Form):
    total_supply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    token_name = StringField("商品名", validators=[Required('商品名は必須です。')])
    token_symbol = StringField("略称", validators=[Required('略称は必須です。')])
    token_decimals = IntegerField("単位", validators=[Required('単位は必須です。')])
    submit = SubmitField('新規発行')

    def __init__(self, issue_token=None, *args, **kwargs):
        super(IssueTokenForm, self).__init__(*args, **kwargs)
        self.issue_token = issue_token

class TokenSettingForm(Form):
    token_address = StringField("トークンアドレス", validators=[Required('トークンアドレスは必須です。')])
    total_supply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    token_name = StringField("商品名", validators=[Required('商品名は必須です。')])
    token_symbol = StringField("略称", validators=[Required('略称は必須です。')])
    token_decimals = IntegerField("単位", validators=[Required('単位は必須です。')])
    image_small = StringField("トークン画像（小）", validators=[])
    image_medium = StringField("トークン画像（中）", validators=[])
    image_large = StringField("トークン画像（大）", validators=[])
    abi = TextAreaField("インターフェース", validators=[Required('ABIは必須です。')])
    bytecode = TextAreaField("バイトコード", validators=[Required('バイトコードは必須です。')])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(TokenSettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting
