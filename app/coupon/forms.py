# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, DateField, HiddenField, DecimalField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from sqlalchemy import or_, and_

class IssueCouponForm(Form):
    name = StringField("商品名", validators=[Required('商品名は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    redemptionDate = StringField("有効期限", validators=[])
    returnAmount = TextAreaField("リターン内容", validators=[])
    image_small = StringField("商品画像（小）URL", validators=[])
    image_medium = StringField("商品画像（中）URL", validators=[])
    image_large = StringField("商品画像（大）URL", validators=[])
    submit = SubmitField('新規発行')

    def __init__(self, issue_coupon=None, *args, **kwargs):
        super(IssueCouponForm, self).__init__(*args, **kwargs)
        self.issue_coupon = issue_coupon

class TransferCouponForm(Form):
    tokenAddress = StringField("債券アドレス", validators=[Required('債券アドレスは必須です。')])
    sendAddress = StringField("割当先アドレス", validators=[Required('割当先アドレスは必須です。')])
    sendAmount = IntegerField("割当数量", validators=[Required('割当数量は必須です。')])
    submit = SubmitField('割当')

    def __init__(self, transfer_coupon=None, *args, **kwargs):
        super(TransferCouponForm, self).__init__(*args, **kwargs)
        self.transfer_coupon = transfer_coupon

