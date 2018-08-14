# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, DateField, HiddenField, DecimalField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from ..models import Role, User
from sqlalchemy import or_, and_

class IssueTokenForm(Form):
    name = StringField("商品名", validators=[Required('商品名は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    faceValue = DecimalField("額面（円）", places=0, validators=[])
    interestRate = DecimalField("金利[税引前]（%）", places=3, validators=[])
    interestPaymentDate1 = StringField("利払日１", validators=[])
    interestPaymentDate2 = StringField("利払日２", validators=[])
    interestPaymentDate3 = StringField("利払日３", validators=[])
    interestPaymentDate4 = StringField("利払日４", validators=[])
    interestPaymentDate5 = StringField("利払日５", validators=[])
    interestPaymentDate6 = StringField("利払日６", validators=[])
    interestPaymentDate7 = StringField("利払日７", validators=[])
    interestPaymentDate8 = StringField("利払日８", validators=[])
    interestPaymentDate9 = StringField("利払日９", validators=[])
    interestPaymentDate10 = StringField("利払日１０", validators=[])
    interestPaymentDate11 = StringField("利払日１１", validators=[])
    interestPaymentDate12 = StringField("利払日１２", validators=[])
    redemptionDate = StringField("償還日", validators=[])
    redemptionAmount = IntegerField("償還金額（額面当り）", validators=[])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = TextAreaField("リターン内容", validators=[])
    purpose = TextAreaField("発行目的", validators=[Required('発行目的は必須です。')])
    memo = TextAreaField("メモ", validators=[])
    submit = SubmitField('新規発行')

    def __init__(self, issue_token=None, *args, **kwargs):
        super(IssueTokenForm, self).__init__(*args, **kwargs)
        self.issue_token = issue_token

class TokenSettingForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("商品名", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    faceValue = IntegerField("額面（円）", validators=[])
    interestRate = DecimalField("金利[税引前]（%）", places=3, validators=[])
    interestPaymentDate1 = StringField("利払日１", validators=[])
    interestPaymentDate2 = StringField("利払日２", validators=[])
    interestPaymentDate3 = StringField("利払日３", validators=[])
    interestPaymentDate4 = StringField("利払日４", validators=[])
    interestPaymentDate5 = StringField("利払日５", validators=[])
    interestPaymentDate6 = StringField("利払日６", validators=[])
    interestPaymentDate7 = StringField("利払日７", validators=[])
    interestPaymentDate8 = StringField("利払日８", validators=[])
    interestPaymentDate9 = StringField("利払日９", validators=[])
    interestPaymentDate10 = StringField("利払日１０", validators=[])
    interestPaymentDate11 = StringField("利払日１１", validators=[])
    interestPaymentDate12 = StringField("利払日１２", validators=[])
    redemptionDate = StringField("償還日", validators=[])
    redemptionAmount = IntegerField("償還金額（額面当り）", validators=[])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = TextAreaField("リターン内容", validators=[])
    purpose = TextAreaField("発行目的", validators=[])
    memo = TextAreaField("メモ", validators=[])
    image_small = StringField("商品画像（小）URL", validators=[])
    image_medium = StringField("商品画像（中）URL", validators=[])
    image_large = StringField("商品画像（大）URL", validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(TokenSettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting

class SellTokenForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("商品名", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    faceValue = IntegerField("額面（円）", validators=[])
    interestRate = DecimalField("金利[税引前]（%）", places=3, validators=[])
    interestPaymentDate1 = StringField("利払日１", validators=[])
    interestPaymentDate2 = StringField("利払日２", validators=[])
    interestPaymentDate3 = StringField("利払日３", validators=[])
    interestPaymentDate4 = StringField("利払日４", validators=[])
    interestPaymentDate5 = StringField("利払日５", validators=[])
    interestPaymentDate6 = StringField("利払日６", validators=[])
    interestPaymentDate7 = StringField("利払日７", validators=[])
    interestPaymentDate8 = StringField("利払日８", validators=[])
    interestPaymentDate9 = StringField("利払日９", validators=[])
    interestPaymentDate10 = StringField("利払日１０", validators=[])
    interestPaymentDate11 = StringField("利払日１１", validators=[])
    interestPaymentDate12 = StringField("利払日１２", validators=[])
    redemptionDate = StringField("償還日", validators=[])
    redemptionAmount = IntegerField("償還金額（額面当り）", validators=[])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = StringField("リターン内容", validators=[])
    purpose = StringField("発行目的", validators=[])
    memo = TextAreaField("メモ", validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    sellPrice = IntegerField("売出価格（額面当り）", validators=[Required('売出価格は必須です。')])
    submit = SubmitField('募集開始')

    def __init__(self, sell_token=None, *args, **kwargs):
        super(SellTokenForm, self).__init__(*args, **kwargs)
        self.sell_token = sell_token

class CancelOrderForm(Form):
    order_id = IntegerField("注文ID", validators=[])
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("商品名", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    amount = IntegerField("募集中数量（残注文数量）", validators=[])
    faceValue = IntegerField("額面", validators=[])
    price = IntegerField("売出価格（額面当り）", validators=[])
    submit = SubmitField('募集停止')

    def __init__(self, cancel_order=None, *args, **kwargs):
        super(CancelOrderForm, self).__init__(*args, **kwargs)
        self.sell_token = cancel_order

class RequestSignatureForm(Form):
    token_address = HiddenField("トークンアドレス", validators=[Required('トークンアドレスは必須です。')])
    signer = StringField("認定者", validators=[Required('認定者は必須です。')])
    submit = SubmitField('認定依頼')

    def __init__(self, request_signature=None, *args, **kwargs):
        super(RequestSignatureForm, self).__init__(*args, **kwargs)
        self.request_signature = request_signature
