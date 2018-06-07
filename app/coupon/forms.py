# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, DateField, HiddenField, DecimalField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from sqlalchemy import or_, and_

class TransferCouponForm(Form):
    tokenAddress = StringField("債券アドレス", validators=[Required('債券アドレスは必須です。')])
    sendAddress = StringField("割当先アドレス", validators=[Required('割当先アドレスは必須です。')])
    sendAmount = IntegerField("割当数量", validators=[Required('割当数量は必須です。')])
    submit = SubmitField('割当')

    def __init__(self, transfer_coupon=None, *args, **kwargs):
        super(TransferCouponForm, self).__init__(*args, **kwargs)
        self.transfer_coupon = transfer_coupon

