# -*- coding:utf-8 -*-
from flask import session
from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, URL, Optional, Length, Regexp, NumberRange
from wtforms import ValidationError

from app.models import Issuer

from web3 import Web3


def max_sell_price(message='{max_sell_price}円が上限です。'):
    """
    最大売出価格バリデータを返す。
    :param message: エラーメッセージ。埋め込み文字列`{max_sell_price}`には最大売出価格が設定される。
    :return:　バリデータ
    """

    def _max_sell_price(form, field):
        issuer = Issuer.query.get(session['issuer_id'])
        if field.data > issuer.max_sell_price:
            raise ValidationError(message.format(max_sell_price=issuer.max_sell_price))

    return _max_sell_price


class IssueForm(Form):
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'

    name = StringField(
        "名称 *",
        validators=[
            DataRequired('名称は必須です。'),
            Length(min=1, max=100, message='名称は100文字以内で入力してください。')
        ]
    )

    symbol = StringField(
        "略称 *",
        validators=[
            DataRequired('略称は必須です。'),
            Regexp('^[a-zA-Z0-9]+$', message='略称は半角英数字で入力してください。'),
            Length(min=1, max=10, message='略称は10文字以内の半角英数字で入力してください。')
        ]
    )

    totalSupply = IntegerField(
        "総発行量 *",
        validators=[
            DataRequired('総発行量は必須です。'),
            NumberRange(min=1, max=100000000, message='総発行量は100,000,000が上限です。'),
        ]
    )

    details = TextAreaField(
        "会員権詳細",
        validators=[
            Length(max=2000, message='会員権詳細は2,000文字以内で入力してください。')
        ]
    )

    return_details = TextAreaField(
        "特典詳細",
        validators=[
            Length(max=2000, message='特典詳細は2,000文字以内で入力してください。')
        ]
    )

    expirationDate = StringField(
        "有効期限",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='有効期限はYYYYMMDDで入力してください。'),
        ]
    )

    memo = TextAreaField(
        "メモ",
        validators=[
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
    )

    transferable = SelectField(
        '譲渡制限',
        choices=[(True, 'True'), (False, 'False')], default='True'
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
            Length(max=5000, message='プライバシーポリシーは5,000文字以内で入力してください。')
        ]
    )

    submit = SubmitField('新規発行')

    def __init__(self, issue_data=None, *args, **kwargs):
        super(IssueForm, self).__init__(*args, **kwargs)
        self.issue_data = issue_data
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]
        self.description = {
            'name': '',
            'symbol': '商品を識別するための略称を設定してください。',
            'totalSupply': '',
            'details': '商品の詳細説明を入力してください。',
            'return_details': '商品を購入することで得られる特典の説明を入力してください。',
            'memo': '商品の補足情報を入力してください。',
            'expirationDate': '商品の有効期限を入力してください。',
            'transferable': '譲渡可能な場合は「なし」、譲渡不可の場合は「あり」を選択してください。',
            'tradableExchange': '商品が取引可能なDEXコントラクトのアドレスを入力してください。',
            'image_1': '商品画像のURLを入力してください。',
            'image_2': '商品画像のURLを入力してください',
            'image_3': '商品画像のURLを入力してください',
            'contact_information': '商品に関する問い合わせ先情報を入力してください。',
            'privacy_policy': '商品に関するプライバシーポリシーを入力してください。',
        }


class SettingForm(Form):
    yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'

    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])

    details = TextAreaField(
        "会員権詳細",
        validators=[
            Length(max=2000, message='会員権詳細は2,000文字以内で入力してください。')
        ])

    return_details = TextAreaField(
        "特典詳細",
        validators=[
            Length(max=2000, message='特典詳細は2,000文字以内で入力してください。')
        ]
    )

    expirationDate = StringField(
        "有効期限",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='有効期限はYYYYMMDDで入力してください。'),
        ]
    )

    memo = TextAreaField(
        "メモ",
        validators=[
            Length(max=2000, message='メモは2,000文字以内で入力してください。')
        ]
    )

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

    contact_information = TextAreaField(
        "問い合わせ先",
        validators=[
            Length(max=2000, message='問い合わせ先は2,000文字以内で入力してください。')
        ]
    )

    privacy_policy = TextAreaField(
        "プライバシーポリシー",
        validators=[
            Length(max=5000, message='プライバシーポリシーは5,000文字以内で入力してください。')
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
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]


class SellForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    details = TextAreaField("会員権詳細", validators=[])
    return_details = TextAreaField("特典詳細", validators=[])
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
            DataRequired('売出価格は必須です。'),
            NumberRange(min=1, message='最低売出価格は1円です。'),
            max_sell_price('売出価格は{max_sell_price}円が上限です。')
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


class TransferForm(Form):
    token_address = StringField(
        "会員権アドレス",
        validators=[
            DataRequired('会員権アドレスは必須です。')
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

    def __init__(self, transfer_membership=None, *args, **kwargs):
        super(TransferForm, self).__init__(*args, **kwargs)
        self.transfer_membership = transfer_membership


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
        chk = None
        if not Web3.isAddress(field.data):
            raise ValidationError('移転先は無効なアドレスです。')


class AddSupplyForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    addSupply = IntegerField(
        "追加発行量",
        validators=[
            DataRequired('追加発行量は必須です。'),
            NumberRange(min=1, max=100000000, message='追加発行量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('追加発行')

    def __init__(self, issue=None, *args, **kwargs):
        super(AddSupplyForm, self).__init__(*args, **kwargs)
        self.issue = issue
