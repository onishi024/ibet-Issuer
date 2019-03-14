# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import Required, URL, Optional, Length, Regexp, NumberRange
from wtforms import ValidationError

from web3 import Web3

class IssueCouponForm(Form):
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'

    name = StringField(
        "クーポン名",
        validators = [
            Required('クーポン名は必須です。'),
            Length(min=1, max=50, message='クーポン名は50文字以内で入力してください。')
        ]
    )

    symbol = StringField(
        "略称",
        validators = [
            Required('略称は必須です。'),
            Regexp('^[a-zA-Z0-9]+$', message='略称は半角英数字で入力してください。'),
            Length(min=1, max=10, message='略称は10文字以内の半角英数字で入力してください。')
        ]
    )

    totalSupply = IntegerField(
        "総発行量",
        validators = [
            Required('総発行量は必須です。'),
            NumberRange(min=1, max=100000000, message='総発行量は100,000,000が上限です。'),
        ]
    )

    expirationDate = StringField(
        "有効期限",
        validators = [
            Optional(),
            Regexp(yyyymmdd_regexp, message='有効期限はYYYYMMDDで入力してください。'),
        ]
    )

    details = TextAreaField(
        "クーポン詳細",
        validators = [
            Length(max=2000, message='クーポン詳細は2,000文字以内で入力してください。')
        ]
    )

    memo = TextAreaField(
        "メモ",
        validators = [
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
    )

    transferable = SelectField(
        '譲渡制限',
        choices=[(True, 'True'), (False, 'False')], default='True'
    )

    image_small = StringField(
        "画像（小）URL",
        validators=[
            Optional(),
            URL(message='画像（小）URLは無効なURLです。')
        ]
    )

    image_medium = StringField(
        "画像（中）URL",
        validators=[
            Optional(),
            URL(message='画像（中）URLは無効なURLです。')
        ]
    )

    image_large = StringField(
        "画像（大）URL",
        validators=[
            Optional(),
            URL(message='画像（大）URLは無効なURLです。')
        ]
    )

    tradableExchange = StringField(
        "DEXアドレス",
        validators=[
            Required('DEXアドレスは必須です。')
        ]
    )

    submit = SubmitField('登録')

    def __init__(self, issue_coupon=None, *args, **kwargs):
        super(IssueCouponForm, self).__init__(*args, **kwargs)
        self.issue_coupon = issue_coupon
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]

class SettingCouponForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("クーポン名", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    expirationDate = StringField("有効期限",validators=[])

    details = TextAreaField(
        "クーポン詳細",
        validators = [
            Length(max=2000, message='クーポン詳細は2,000文字以内で入力してください。')
        ])

    memo = TextAreaField(
        "メモ",
        validators = [
            Length(max=2000, message='メモは2,000文字以内の半角英数字で入力してください。')
        ]
    )

    transferable = SelectField(
        '譲渡制限',
        choices=[(True, 'True'), (False, 'False')],
        default='True'
    )

    image_small = StringField(
        "画像（小）URL",
        validators=[
            Optional(), URL(message='画像（小）URLは無効なURLです。')
        ]
    )

    image_medium = StringField(
        "画像（中）URL",
        validators=[
            Optional(),
            URL(message='画像（中）URLは無効なURLです。')
        ]
    )

    image_large = StringField(
        "画像（大）URL",
        validators=[
            Optional(),
            URL(message='画像（大）URLは無効なURLです。')
        ]
    )

    tradableExchange = StringField(
        "DEXアドレス",
        validators=[]
    )

    abi = TextAreaField(
        "インターフェース",
        validators=[]
    )

    bytecode = TextAreaField(
        "バイトコード",
        validators=[]
    )

    submit = SubmitField('設定変更')

    def __init__(self, coupon_setting=None, *args, **kwargs):
        super(SettingCouponForm, self).__init__(*args, **kwargs)
        self.coupon_setting = coupon_setting
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]

class AddSupplyForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("クーポン名", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    addSupply = IntegerField(
        "追加発行する数量",
        validators = [
            Required('追加発行する数量は必須です。'),
            NumberRange(min=1, max=100000000, message='追加発行量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('追加発行')

    def __init__(self, issue_coupon=None, *args, **kwargs):
        super(AddSupplyForm, self).__init__(*args, **kwargs)
        self.issue_coupon = issue_coupon

class TransferForm(Form):
    token_address = StringField(
        "クーポンアドレス",
        validators=[
            Required('クーポンアドレスは必須です。')
        ]
    )

    to_address = StringField(
        "割当先アドレス",
        validators=[
            Required('割当先アドレスは必須です。')
        ]
    )

    amount = IntegerField(
        "割当数量",
        validators=[
            Required('割当数量は必須です。'),
            NumberRange(min=1, max=100000000, message='割当数量は100,000,000が上限です。'),
        ]
    )

    submit = SubmitField('割当')

    def __init__(self, transfer_coupon=None, *args, **kwargs):
        super(TransferForm, self).__init__(*args, **kwargs)
        self.transfer_coupon = transfer_coupon

class TransferOwnershipForm(Form):
    from_address = StringField("現在の所有者（アドレス）",validators = [])
    to_address = StringField(
        "移転先（アドレス）",
        validators = [
            Required('移転先は必須です。')
        ]
    )
    amount = IntegerField(
        "移転数量",
        validators = [
            Required('移転数量は必須です。'),
            NumberRange(min=1, max=100000000, message='移転数量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('移転')

    def __init__(self, transfer_ownership=None, *args, **kwargs):
        super(TransferOwnershipForm, self).__init__(*args, **kwargs)
        self.transfer_ownership = transfer_ownership

    def validate_to_address(self, field):
        chk = None
        if not Web3.isAddress(field.data):
            raise ValidationError('移転先は無効なアドレスです。')

class SellForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    details = TextAreaField("詳細", validators=[])
    expirationDate = StringField("有効期限", validators=[])
    memo = TextAreaField("メモ", validators=[])
    tradableExchange = StringField("DEXアドレス", validators=[])
    transferable = StringField('譲渡制限', validators=[])
    status = StringField('取扱ステータス', validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])

    sellPrice = IntegerField(
        "売出価格",
        validators=[
            Required('売出価格は必須です。'),
            NumberRange(min=1, max=6000000, message='売出価格は6,000,000円が上限です。'),
        ]
    )

    submit = SubmitField('売出開始')

    def __init__(self, sell_token=None, *args, **kwargs):
        super(SellForm, self).__init__(*args, **kwargs)
        self.sell_token = sell_token

class CancelOrderForm(Form):
    order_id = IntegerField("注文ID", validators=[])
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    amount = IntegerField("売出中数量（残注文数量）", validators=[])
    price = IntegerField("売出価格", validators=[])
    submit = SubmitField('売出停止')

    def __init__(self, cancel_order=None, *args, **kwargs):
        super(CancelOrderForm, self).__init__(*args, **kwargs)
        self.sell_token = cancel_order
