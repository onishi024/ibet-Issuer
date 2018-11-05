# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, DateField, HiddenField, DecimalField, SelectField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError

class IssueForm(Form):
    name = StringField("名称", validators=[Required('名称は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    details = TextAreaField("会員権詳細", validators=[])
    returnDetails = TextAreaField("リターン詳細", validators=[])
    expirationDate = StringField("有効期限", validators=[])
    memo = TextAreaField("メモ", validators=[])
    transferable = SelectField('譲渡制限', coerce=str, default='True')
    image_small = StringField("画像（小）URL", validators=[])
    image_medium = StringField("画像（中）URL", validators=[])
    image_large = StringField("画像（大）URL", validators=[])
    submit = SubmitField('新規発行')

    def __init__(self, issue_data=None, *args, **kwargs):
        super(IssueForm, self).__init__(*args, **kwargs)
        self.issue_data = issue_data
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]

class SettingForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[Required('名称は必須です。')])
    symbol = StringField("略称", validators=[Required('略称は必須です。')])
    totalSupply = IntegerField("総発行量", validators=[Required('総発行量は必須です。')])
    details = TextAreaField("会員権詳細", validators=[])
    returnDetails = TextAreaField("リターン詳細", validators=[])
    expirationDate = StringField("有効期限", validators=[])
    memo = TextAreaField("メモ", validators=[])
    transferable = SelectField('譲渡制限', coerce=str, default='True')
    image_small = StringField("画像（小）URL", validators=[])
    image_medium = StringField("画像（中）URL", validators=[])
    image_large = StringField("画像（大）URL", validators=[])
    status = SelectField('取扱ステータス', coerce=bool, default=True)

    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(SettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]

class SellForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    details = TextAreaField("会員権詳細", validators=[])
    returnDetails = TextAreaField("リターン詳細", validators=[])
    expirationDate = StringField("有効期限", validators=[])
    memo = TextAreaField("メモ", validators=[])
    transferable = StringField('譲渡制限', validators=[])
    status = StringField('取扱ステータス', validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    sellPrice = IntegerField("売出価格", validators=[Required('売出価格は必須です。')])
    submit = SubmitField('募集開始')

    def __init__(self, sell_token=None, *args, **kwargs):
        super(SellForm, self).__init__(*args, **kwargs)
        self.sell_token = sell_token

class CancelOrderForm(Form):
    order_id = IntegerField("注文ID", validators=[])
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    amount = IntegerField("募集中数量（残注文数量）", validators=[])
    price = IntegerField("売出価格", validators=[])
    submit = SubmitField('募集停止')

    def __init__(self, cancel_order=None, *args, **kwargs):
        super(CancelOrderForm, self).__init__(*args, **kwargs)
        self.sell_token = cancel_order

class AddSupplyForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    addSupply = IntegerField("追加発行する数量", validators=[Required('追加発行する数量は必須です。')])
    submit = SubmitField('追加発行')

    def __init__(self, issue=None, *args, **kwargs):
        super(AddSupplyForm, self).__init__(*args, **kwargs)
        self.issue = issue