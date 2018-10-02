# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, DateField, HiddenField, DecimalField, SelectField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from sqlalchemy import or_, and_

class IssueCouponForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("クーポン名", validators=[Required('クーポン名は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    expirationDate = StringField("有効期限", validators=[])
    details = TextAreaField("クーポン詳細", validators=[])
    isValid = TextAreaField("有効/無効", validators=[])
    memo = TextAreaField("メモ", validators=[])
    transferable = SelectField('譲渡制限', coerce=str, default='False')
    image_small = StringField("商品画像（小）URL", validators=[])
    image_medium = StringField("商品画像（中）URL", validators=[])
    image_large = StringField("商品画像（大）URL", validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    submit = SubmitField('登録')

    def __init__(self, issue_coupon=None, *args, **kwargs):
        super(IssueCouponForm, self).__init__(*args, **kwargs)
        self.issue_coupon = issue_coupon
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]

class AddSupplyForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("クーポン名", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    addSupply = IntegerField("追加発行する数量", validators=[Required('追加発行する数量は必須です。')])
    submit = SubmitField('追加発行')

    def __init__(self, issue_coupon=None, *args, **kwargs):
        super(AddSupplyForm, self).__init__(*args, **kwargs)
        self.issue_coupon = issue_coupon


class TransferCouponForm(Form):
    tokenAddress = StringField("クーポンアドレス", validators=[Required('クーポンアドレスは必須です。')])
    sendAddress = StringField("割当先アドレス", validators=[Required('割当先アドレスは必須です。')])
    sendAmount = IntegerField("割当数量", validators=[Required('割当数量は必須です。')])
    submit = SubmitField('割当')

    def __init__(self, transfer_coupon=None, *args, **kwargs):
        super(TransferCouponForm, self).__init__(*args, **kwargs)
        self.transfer_coupon = transfer_coupon
