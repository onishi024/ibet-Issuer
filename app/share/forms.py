# -*- coding:utf-8 -*-
import math

from flask_wtf import FlaskForm as Form

from wtforms import IntegerField, StringField, TextAreaField, \
    SubmitField, HiddenField, DecimalField, SelectField
from wtforms.validators import DataRequired, URL, Optional, Length, Regexp, \
    NumberRange, InputRequired
from wtforms import ValidationError
from config import Config

from web3 import Web3


# アドレス形式のバリデータ
def address(message='有効なアドレスではありません'):
    def _address(form, field):
        if not Web3.isAddress(field.data):
            raise ValidationError(message)

    return _address


# トークン新規発行
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
            InputRequired('総発行量は必須です。'),
            NumberRange(min=0, max=100_000_000, message='総発行量は100,000,000が上限です。'),
        ]
    )

    issuePrice = IntegerField(
        "発行価格（円） *",
        validators=[
            InputRequired('発行価格は必須です。'),
            NumberRange(min=0, max=5_000_000_000, message='発行価格は5,000,000,000円が上限です。')
        ]
    )

    dividends = IntegerField(
        "1口あたりの配当金/分配金",
        validators=[
            InputRequired('1口あたりの配当金/分配金は必須です。'),
            NumberRange(min=0, max=5_000_000_000, message='1口あたりの配当金/分配金は5,000,000,000円が上限です。')
        ]
    )

    dividendRecordDate = StringField(
        "権利確定日",
        validators=[
            InputRequired('権利確定日は必須です。'),
            Regexp(yyyymmdd_regexp, message='権利確定日はYYYYMMDDで入力してください。'),
        ]
    )

    dividendPaymentDate = StringField(
        "配当支払日",
        validators=[
            InputRequired('配当支払日は必須です。'),
            Regexp(yyyymmdd_regexp, message='配当支払日はYYYYMMDDで入力してください。'),
        ]
    )

    cansellationDate = StringField(
        "消却日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='消却日はYYYYMMDDで入力してください。')
        ]
    )

    memo = TextAreaField(
        "補足情報",
        validators=[
            Length(max=2000, message='補足情報は2,000文字以内で入力してください。')
        ]
    )

    transferable = SelectField(
        '譲渡制限',
        choices=[(True, 'True'), (False, 'False')], default='True'
    )

    referenceUrls_1 = StringField(
        "関連URL（１）",
        validators=[
            Optional(),
            URL(message='関連URL（１）は無効なURLです。')
        ]
    )

    referenceUrls_2 = StringField(
        "関連URL（２）",
        validators=[
            Optional(),
            URL(message='関連URL（２）は無効なURLです。')
        ]
    )

    referenceUrls_3 = StringField(
        "関連URL（３）",
        validators=[
            Optional(),
            URL(message='関連URL（３）は無効なURLです。')
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

    tradableExchange = StringField(
        "DEXアドレス",
        validators=[
            DataRequired('DEXアドレスは必須です。'),
            address('DEXアドレスは有効なアドレスではありません。')
        ]
    )

    personalInfoAddress = StringField(
        "個人情報コントラクト",
        validators=[
            DataRequired('個人情報コントラクトアドレスは必須です。'),
            address('個人情報コントラクトアドレスは有効なアドレスではありません。')
        ]
    )

    submit = SubmitField('新規発行')

    def __init__(self, issue_token=None, *args, **kwargs):
        super(IssueForm, self).__init__(*args, **kwargs)
        self.issue_token = issue_token
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]
        self.description = {
            'name': '',
            'symbol': '商品を識別するための略称を設定してください。',
            'totalSupply': '',
            'issuePrice': '',
            'dividends': '',
            'dividendRecordDate': '',
            'dividendPaymentDate': '',
            'cansellationDate': '',
            'transferable': '譲渡可能な場合は「なし」、譲渡不可の場合は「あり」を選択してください。。',
            'memo': '商品の補足情報を入力してください。',
            'tradableExchange': '商品が取引可能なDEXコントラクトのアドレスを入力してください。',
            'personalInfoAddress': '所有者名義情報を管理するコントラクトのアドレスを入力してください。',
            'contact_information': '商品に関する問い合わせ先情報を入力してください。',
            'privacy_policy': '商品に関するプライバシーポリシーを入力してください。',
        }
