# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, PasswordField, SubmitField, HiddenField, SelectField, PasswordField, FileField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from ..models import Role, User
from sqlalchemy import or_, and_

class IssueTokenForm(Form):
    name = StringField("商品名", validators=[Required('商品名は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    faceValue = IntegerField("額面", validators=[Required('額面は必須です。')])
    interestRate = IntegerField("金利", validators=[Required('金利は必須です。')])
    interestPaymentDate1 = StringField("利払日１", validators=[])
    interestPaymentDate2 = StringField("利払日２", validators=[])
    redemptionDate = StringField("償還日", validators=[Required('償還日は必須です。')])
    redemptionAmount = IntegerField("償還金額", validators=[Required('償還金額は必須です。')])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = TextAreaField("リターン内容", validators=[])
    purpose = TextAreaField("発行目的", validators=[Required('発行目的は必須です。')])
    image_small = StringField("トークン画像（小）URL", validators=[])
    image_medium = StringField("トークン画像（中）URL", validators=[])
    image_large = StringField("トークン画像（大）URL", validators=[])
    submit = SubmitField('新規発行')

    def __init__(self, issue_token=None, *args, **kwargs):
        super(IssueTokenForm, self).__init__(*args, **kwargs)
        self.issue_token = issue_token

class TokenSettingForm(Form):
    token_address = StringField("トークンアドレス", validators=[Required('トークンアドレスは必須です。')])
    name = StringField("商品名", validators=[Required('商品名は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    faceValue = IntegerField("額面", validators=[Required('額面は必須です。')])
    interestRate = IntegerField("金利", validators=[Required('金利は必須です。')])
    interestPaymentDate1 = StringField("利払日１", validators=[])
    interestPaymentDate2 = StringField("利払日２", validators=[])
    redemptionDate = StringField("償還日", validators=[Required('償還日は必須です。')])
    redemptionAmount = IntegerField("償還金額", validators=[Required('償還金額は必須です。')])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = StringField("リターン内容", validators=[])
    purpose = StringField("発行目的", validators=[Required('発行目的は必須です。')])
    image_small = StringField("トークン画像（小）URL", validators=[])
    image_medium = StringField("トークン画像（中）URL", validators=[])
    image_large = StringField("トークン画像（大）URL", validators=[])
    abi = TextAreaField("インターフェース", validators=[Required('ABIは必須です。')])
    bytecode = TextAreaField("バイトコード", validators=[Required('バイトコードは必須です。')])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(TokenSettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting

class SellTokenForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("商品名", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    faceValue = IntegerField("額面", validators=[])
    interestRate = IntegerField("金利", validators=[])
    interestPaymentDate1 = StringField("利払日１", validators=[])
    interestPaymentDate2 = StringField("利払日２", validators=[])
    redemptionDate = StringField("償還日", validators=[])
    redemptionAmount = IntegerField("償還金額", validators=[])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = StringField("リターン内容", validators=[])
    purpose = StringField("発行目的", validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    sellPrice = IntegerField("売出価格", validators=[Required('売出価格は必須です。')])
    submit = SubmitField('募集開始')

    def __init__(self, sell_token=None, *args, **kwargs):
        super(SellTokenForm, self).__init__(*args, **kwargs)
        self.sell_token = sell_token
