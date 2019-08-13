# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, URL, Optional, Length, Regexp, NumberRange
from wtforms import ValidationError

from web3 import Web3


# +++++++++++++++++++++++++++++++
# 新規発行
# +++++++++++++++++++++++++++++++
class IssueForm(Form):
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'
    name = StringField(
        "名称",
        validators=[
            DataRequired('名称は必須です。'),
            Length(min=1, max=50, message='名称は50文字以内で入力してください。')
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
    details = TextAreaField(
        "詳細",
        validators=[
            Length(max=2000, message='詳細は2,000文字以内で入力してください。')
        ]
    )
    memo = TextAreaField(
        "メモ",
        validators=[
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
    )
    image_1 = StringField(
        "画像（１）URL",
        validators=[
            Optional(),
            URL(message='画像（１）URLは無効なURLです。')
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
        validators=[
            DataRequired('DEXアドレスは必須です。')
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

    def __init__(self, issue_data=None, *args, **kwargs):
        super(IssueForm, self).__init__(*args, **kwargs)
        self.issue_data = issue_data
        self.description = {
            'name': '',
            'symbol': '商品を識別するための略称を設定してください。',
            'totalSupply': '',
            'details': '商品を識別するための略称を設定してください。',
            'memo': '商品の補足情報を入力してください。',
            'tradableExchange': '商品が取引可能な取引所コントラクトのアドレスを入力してください。',
            'image_1': '商品画像のURLを入力してください。',
            'image_2': '商品画像のURLを入力してください。',
            'image_3': '商品画像のURLを入力してください。',
            'contact_information': '商品に関する問い合わせ先情報を入力してください。',
            'privacy_policy': '商品に関するプライバシーポリシーを入力してください。',
        }


# +++++++++++++++++++++++++++++++
# 設定変更
# +++++++++++++++++++++++++++++++
class SettingForm(Form):
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    details = TextAreaField(
        "詳細",
        validators=[
            Length(max=2000, message='詳細は2,000文字以内で入力してください。')
        ]
    )
    memo = TextAreaField(
        "メモ",
        validators=[
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
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
    abi = TextAreaField(
        "インターフェース",
        validators=[]
    )
    bytecode = TextAreaField(
        "バイトコード",
        validators=[]
    )
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(SettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting


# +++++++++++++++++++++++++++++++
# 保有者移転
# +++++++++++++++++++++++++++++++
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


# +++++++++++++++++++++++++++++++
# 割当
# +++++++++++++++++++++++++++++++
class TransferForm(Form):
    token_address = StringField(
        "トークンアドレス",
        validators=[
            DataRequired('トークンアドレスは必須です。')
        ]
    )

    to_address = StringField(
        "割当先アドレス",
        validators=[
            DataRequired('割当先アドレスは必須です。')
        ]
    )

    amount = IntegerField(
        "割当数量",
        validators=[
            DataRequired('割当数量は必須です。'),
            NumberRange(min=1, max=100000000, message='割当数量は100,000,000が上限です。'),
        ]
    )

    submit = SubmitField('割当')

    def __init__(self, transfer_coupon=None, *args, **kwargs):
        super(TransferForm, self).__init__(*args, **kwargs)
        self.transfer_coupon = transfer_coupon


# +++++++++++++++++++++++++++++++
# 償却
# +++++++++++++++++++++++++++++++
class BurnForm(Form):
    account_address = StringField("所有者")
    balance = IntegerField("現在の残高")
    burn_amount = IntegerField(
        "償却数量",
        validators=[
            DataRequired('償却数量は必須です。'),
            NumberRange(min=1, max=100000000, message='償却数量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('償却')

    def __init__(self, burn=None, *args, **kwargs):
        super(BurnForm, self).__init__(*args, **kwargs)
        self.burn = burn


# +++++++++++++++++++++++++++++++
# 追加発行
# +++++++++++++++++++++++++++++++
class AdditionalIssueForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    total_supply = IntegerField("総発行量", validators=[])
    amount = IntegerField(
        "追加発行量",
        validators=[
            DataRequired('追加発行量は必須です。'),
            NumberRange(min=1, max=100000000, message='追加発行量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('追加発行')

    def __init__(self, issue=None, *args, **kwargs):
        super(AdditionalIssueForm, self).__init__(*args, **kwargs)
        self.issue = issue
