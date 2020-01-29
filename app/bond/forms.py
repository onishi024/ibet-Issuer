# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, HiddenField, DecimalField, SelectField
from wtforms.validators import DataRequired, URL, Optional, Length, Regexp, \
    NumberRange
from wtforms import ValidationError
from config import Config

from web3 import Web3


# トークン新規発行
class IssueForm(Form):
    mmdd_regexp = '^(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'

    name = StringField(
        "商品名",
        validators=[
            DataRequired('商品名は必須です。'),
            Length(min=1, max=50, message='商品名は50文字以内で入力してください。')
        ]
    )

    symbol = StringField(
        "略称",
        validators=[
            DataRequired('略称は必須です。'),
            Regexp('^[a-zA-Z0-9]+$', message='略称は半角英数字で入力してください。'),
            Length(min=1, max=10, message='略称は10文字以内の半角英数字で入力してください。')
        ]
    )

    totalSupply = IntegerField(
        "総発行量",
        validators=[
            DataRequired('総発行量は必須です。'),
            NumberRange(min=1, max=100000000, message='総発行量は100,000,000が上限です。'),
        ]
    )

    faceValue = IntegerField(
        "額面（円）",
        validators=[
            NumberRange(min=0, max=5000000000, message='額面は5,000,000,000円が上限です。')
        ]
    )

    interestRate = DecimalField(
        "金利[税引前]（%）",
        places=3,
        validators=[
            NumberRange(min=0.000, max=100.000, message='金利は100％が上限です。')
        ]
    )

    interestPaymentDate1 = StringField(
        "利払日１",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日１はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate2 = StringField(
        "利払日２",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日２はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate3 = StringField(
        "利払日３",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日３はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate4 = StringField(
        "利払日４",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日４はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate5 = StringField(
        "利払日５",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日５はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate6 = StringField(
        "利払日６",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日６はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate7 = StringField(
        "利払日７",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日７はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate8 = StringField(
        "利払日８",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日８はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate9 = StringField(
        "利払日９",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日９はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate10 = StringField(
        "利払日１０",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日１０はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate11 = StringField(
        "利払日１１",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日１１はMMDDで入力してください。'),
        ]
    )

    interestPaymentDate12 = StringField(
        "利払日１２",
        validators=[
            Optional(),
            Regexp(mmdd_regexp, message='利払日１２はMMDDで入力してください。'),
        ]
    )

    redemptionDate = StringField(
        "償還日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='償還日はYYYYMMDDで入力してください。'),
        ]
    )

    redemptionValue = IntegerField(
        "償還金額（額面当り）",
        validators=[
            NumberRange(min=0, max=5000000000, message='償還金額は5,000,000,000円が上限です。')
        ]
    )

    returnDate = StringField(
        "リターン実施日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='リターン実施日はYYYYMMDDで入力してください。'),
        ]
    )

    returnAmount = TextAreaField(
        "リターン内容",
        validators=[
            Length(max=2000, message='リターン内容は2,000文字以内で入力してください。')
        ]
    )

    purpose = TextAreaField(
        "発行目的",
        validators=[
            DataRequired('発行目的は必須です。'),
            Length(max=2000, message='発行目的は2,000文字以内で入力してください。')
        ]
    )

    memo = TextAreaField(
        "メモ",
        validators=[
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
    )

    tradableExchange = StringField(
        "DEXアドレス",
        validators=[
            DataRequired('DEXアドレスは必須です。')
        ]
    )

    personalInfoAddress = StringField(
        "個人情報コントラクト",
        validators=[
            DataRequired('個人情報コントラクトアドレスは必須です。')
        ]
    )

    contact_information = TextAreaField(
        "問い合わせ先",
        validators=[
            Length(max=2000, message='問い合わせ先は2,000文字以内で入力してください。')
        ]
    )

    privacy_policy = TextAreaField(
        "プライバシーポリシー",
        validators=[
            Length(max=2000, message='プライバシーポリシーは2,000文字以内で入力してください。')
        ]
    )

    submit = SubmitField('新規発行')

    def __init__(self, issue_token=None, *args, **kwargs):
        super(IssueForm, self).__init__(*args, **kwargs)
        self.issue_token = issue_token
        self.description = {
            'name': '',
            'symbol': '商品を識別するための略称を設定してください。',
            'totalSupply': '',
            'faceValue': '',
            'interestRate': '税引前金利を入力してください。',
            'interestPaymentDate': '',
            'redemptionDate': '',
            'redemptionValue': '額面当りの償還金額を入力してください。',
            'returnDate': 'リターンを実施する日付を入力してください。',
            'returnAmount': '商品を購入することで得られるリターン（特典）の内容を入力してください。',
            'purpose': '商品の発行目的を入力してください。',
            'memo': '商品の補足情報を入力してください。',
            'tradableExchange': '商品が取引可能な取引所コントラクトのアドレスを入力してください。',
            'personalInfoAddress': '所有者名義情報を管理するコントラクトのアドレスを入力してください。',
            'contact_information': '商品に関する問い合わせ先情報を入力してください。',
            'privacy_policy': '商品に関するプライバシーポリシーを入力してください。',
        }


# トークン設定変更
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
    redemptionValue = IntegerField("償還金額（額面当り）", validators=[])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = TextAreaField("リターン内容", validators=[])
    purpose = TextAreaField("発行目的", validators=[])
    memo = TextAreaField("メモ", validators=[])

    transferable = SelectField(
        '譲渡制限',
        choices=[(True, 'True'), (False, 'False')],
        default='True'
    )

    image_1 = StringField(
        "画像（１）URL",
        validators=[
            Optional(), URL(message='画像（１）URLは無効なURLです。')
        ]
    )

    image_2 = StringField(
        "画像（２）URL",
        validators=[
            Optional(),
            URL(message='画像（２）URLは無効なURLです。')
        ]
    )

    image_3 = StringField(
        "画像（３）URL",
        validators=[
            Optional(),
            URL(message='画像（３）URLは無効なURLです。')
        ]
    )

    tradableExchange = StringField(
        "DEXアドレス",
        validators=[]
    )

    personalInfoAddress = StringField(
        "個人情報コントラクト",
        validators=[]
    )

    contact_information = TextAreaField(
        "問い合わせ先",
        validators=[
            Length(max=2000, message='問い合わせ先は2,000文字以内で入力してください。')
        ]
    )

    privacy_policy = TextAreaField(
        "プライバシーポリシー",
        validators=[
            Length(max=2000, message='プライバシーポリシーは2,000文字以内で入力してください。')
        ]
    )

    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(SettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]


# 売出
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
    redemptionValue = IntegerField("償還金額（額面当り）", validators=[])
    returnDate = StringField("リターン実施日", validators=[])
    returnAmount = TextAreaField("リターン内容", validators=[])
    purpose = TextAreaField("発行目的", validators=[])
    memo = TextAreaField("メモ", validators=[])
    tradableExchange = StringField("DEXアドレス", validators=[])
    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])

    message = '売出価格は' + str(Config.MAX_SELL_PRICE) + '円が上限です。'
    sellPrice = IntegerField(
        "売出価格（額面当り）",
        validators=[
            DataRequired('売出価格は必須です。'),
            NumberRange(min=1, max=int(Config.MAX_SELL_PRICE), message=message),
        ]
    )

    submit = SubmitField('売出開始')

    def __init__(self, sell_token=None, *args, **kwargs):
        super(SellTokenForm, self).__init__(*args, **kwargs)
        self.sell_token = sell_token


# 売出停止（注文取消）
class CancelOrderForm(Form):
    order_id = IntegerField("注文ID", validators=[])
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("商品名", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    amount = IntegerField("売出中数量（残注文数量）", validators=[])
    faceValue = IntegerField("額面", validators=[])
    price = IntegerField("売出価格（額面当り）", validators=[])
    submit = SubmitField('売出停止')

    def __init__(self, cancel_order=None, *args, **kwargs):
        super(CancelOrderForm, self).__init__(*args, **kwargs)
        self.sell_token = cancel_order


# 認定依頼
class RequestSignatureForm(Form):
    token_address = HiddenField("トークンアドレス", validators=[DataRequired('トークンアドレスは必須です。')])
    signer = StringField("認定者", validators=[DataRequired('認定者は必須です。')])
    submit = SubmitField('認定依頼')

    def __init__(self, request_signature=None, *args, **kwargs):
        super(RequestSignatureForm, self).__init__(*args, **kwargs)
        self.request_signature = request_signature


# 権利移転（募集申込）
class TransferForm(Form):
    token_address = StringField(
        "債券アドレス",
        validators=[
            DataRequired('債券アドレスは必須です。')
        ]
    )

    to_address = StringField(
        "移転先",
        validators=[
            DataRequired('移転先は必須です。')
        ]
    )

    amount = IntegerField(
        "移転数量",
        validators=[
            DataRequired('移転数量を入力してください。'),
            NumberRange(min=1, max=100000000, message='移転数量は100,000,000が上限です。'),
        ]
    )

    submit = SubmitField('移転')

    def __init__(self, transfer_bond=None, *args, **kwargs):
        super(TransferForm, self).__init__(*args, **kwargs)
        self.transfer_bond = transfer_bond

    def validate_token_address(self, field):
        if not Web3.isAddress(field.data):
            raise ValidationError('債券アドレスは無効なアドレスです。')

    def validate_to_address(self, field):
        if not Web3.isAddress(field.data):
            raise ValidationError('移転先は無効なアドレスです。')


# 募集申込割当
class AllotForm(Form):
    token_address = StringField(
        "債券アドレス",
        validators=[
            DataRequired('債券アドレスは必須です。')
        ]
    )
    to_address = StringField(
        "割当先",
        validators=[
            DataRequired('割当先は必須です。')
        ]
    )
    amount = IntegerField(
        "割当数量",
        validators=[
            DataRequired('割当数量を入力してください。'),
            NumberRange(min=1, max=100000000, message='割当数量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('割当')

    def __init__(self, allot_bond=None, *args, **kwargs):
        super(AllotForm, self).__init__(*args, **kwargs)
        self.allot_bond = allot_bond


# 所有者移転
class TransferOwnershipForm(Form):
    from_address = StringField("現在の所有者", validators=[])
    to_address = StringField(
        "移転先",
        validators=[
            DataRequired('移転先は必須です。')
        ]
    )
    amount = IntegerField(
        "移転数量",
        validators=[
            DataRequired('移転数量は必須です。'),
            NumberRange(min=1, max=100000000, message='移転数量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('移転')

    def __init__(self, transfer_ownership=None, *args, **kwargs):
        super(TransferOwnershipForm, self).__init__(*args, **kwargs)
        self.transfer_ownership = transfer_ownership

    def validate_to_address(self, field):
        if not Web3.isAddress(field.data):
            raise ValidationError('移転先は無効なアドレスです。')
