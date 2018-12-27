# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, DateField, HiddenField, DecimalField
from wtforms.validators import Required, URL, Optional, Length, Regexp, \
    NumberRange
from wtforms import ValidationError

from web3 import Web3

class IssueForm(Form):
    mmdd_regexp = '^(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'

    name = StringField(
        "商品名",
        validators = [
            Required('商品名は必須です。'),
            Length(min=1, max=50, message='商品名は50文字以内で入力してください。')
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

    faceValue = IntegerField(
        "額面（円）",
        validators = [
            NumberRange(min=0, max=5000000000, message='額面は5,000,000,000円が上限です。')
        ],
        default=0
    )

    interestRate = DecimalField(
        "金利[税引前]（%）",
        places=3,
        validators = [
            NumberRange(min=0.000, max=100.000, message='金利は100％が上限です。')
        ],
        default=0
    )

    interestPaymentDate1 = StringField(
        "利払日１",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日１はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate2 = StringField(
        "利払日２",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日２はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate3 = StringField(
        "利払日３",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日３はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate4 = StringField(
        "利払日４",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日４はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate5 = StringField(
        "利払日５",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日５はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate6 = StringField(
        "利払日６",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日６はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate7 = StringField(
        "利払日７",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日７はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate8 = StringField(
        "利払日８",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日８はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate9 = StringField(
        "利払日９",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日９はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate10 = StringField(
        "利払日１０",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日１０はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate11 = StringField(
        "利払日１１",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日１１はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate12 = StringField(
        "利払日１２",
        validators = [
            Optional(),
            Regexp(mmdd_regexp, message='利払日１２はMMDDで入力してください。'),
        ]
    )

    redemptionDate = StringField(
        "償還日",
        validators = [
            Optional(),
            Regexp(yyyymmdd_regexp, message='償還日はYYYYMMDDで入力してください。'),
        ]
    )

    redemptionAmount = IntegerField(
        "償還金額（額面当り）",
        validators = [
            NumberRange(min=0, max=5000000000, message='償還金額は5,000,000,000円が上限です。')
        ],
        default=0
    )

    returnDate = StringField(
        "リターン実施日",
        validators = [
            Optional(),
            Regexp(yyyymmdd_regexp, message='リターン実施日はYYYYMMDDで入力してください。'),
        ]
    )

    returnAmount = TextAreaField(
        "リターン内容",
        validators = [
            Length(max=2000, message='リターン内容は2,000文字以内で入力してください。')
        ]
    )

    purpose = TextAreaField(
        "発行目的",
        validators = [
            Required('発行目的は必須です。'),
            Length(max=2000, message='発行目的は2,000文字以内で入力してください。')
        ]
    )

    memo = TextAreaField(
        "メモ",
        validators = [
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
    )

    tradableExchange = StringField(
        "DEXアドレス",
        validators=[
            Required('DEXアドレスは必須です。')
        ]
    )

    submit = SubmitField('新規発行')

    def __init__(self, issue_token=None, *args, **kwargs):
        super(IssueForm, self).__init__(*args, **kwargs)
        self.issue_token = issue_token

class SettingForm(Form):
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

    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(SettingForm, self).__init__(*args, **kwargs)
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
    tradableExchange = StringField("DEXアドレス", validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])

    sellPrice = IntegerField(
        "売出価格（額面当り）",
        validators=[
            Required('売出価格は必須です。'),
            NumberRange(min=1, max=6000000, message='売出価格は6,000,000円が上限です。'),
        ]
    )

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