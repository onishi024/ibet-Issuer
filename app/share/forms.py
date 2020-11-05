"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

import math

from flask_wtf import FlaskForm as Form
from web3 import Web3
from wtforms import IntegerField, DecimalField, StringField, TextAreaField, SubmitField, SelectField
from wtforms import ValidationError
from wtforms.validators import DataRequired, URL, Optional, Length, Regexp, NumberRange, InputRequired


# アドレス形式のバリデータ
def address(message='有効なアドレスではありません'):
    def _address(form, field):
        if not Web3.isAddress(field.data):
            raise ValidationError(message)

    return _address


yyyymmdd_regexp = '^(19[0-9]{2}|20[0-9]{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$'


# トークン新規発行
class IssueForm(Form):
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

    dividends = DecimalField(
        "１株配当",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0.00, max=5_000_000_000.00, message='１株配当は5,000,000,000円が上限です。')
        ]
    )

    dividendRecordDate = StringField(
        "権利確定日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='権利確定日はYYYYMMDDで入力してください。'),
        ]
    )

    dividendPaymentDate = StringField(
        "配当支払日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='配当支払日はYYYYMMDDで入力してください。'),
        ]
    )

    cancellationDate = StringField(
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
            'cancellationDate': '',
            'transferable': '譲渡可能な場合は「なし」、譲渡不可の場合は「あり」を選択してください。',
            'memo': '商品の補足情報を入力してください。',
            'tradableExchange': '商品が取引可能なDEXコントラクトのアドレスを入力してください。',
            'personalInfoAddress': '所有者名義情報を管理するコントラクトのアドレスを入力してください。',
            'contact_information': '商品に関する問い合わせ先情報を入力してください。',
            'privacy_policy': '商品に関するプライバシーポリシーを入力してください。',
        }

    @staticmethod
    def check_decimal_places(places, field):
        """
        有効小数点桁数チェック
        :param places: 小数点以下有効桁数：整数
        :param field: 桁数チェックを行う変数：小数（Form）
        :return: 真偽値
        """
        float_data = float(field.data * 10**places)  # 小数点以下5桁目が存在する場合は小数になる
        int_data = int(field.data * 10**places)  # 小数部は切り捨て
        return math.isclose(int_data, float_data)


# トークン設定変更
class SettingForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    symbol = StringField("略称", validators=[])
    totalSupply = IntegerField("総発行量", validators=[])
    issuePrice = IntegerField("発行価格（円）", validators=[])

    dividends = DecimalField(
        "１株配当",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0.00, max=5_000_000_000.00, message='1株配当は5,000,000,000円が上限です。')
        ]
    )

    dividendRecordDate = StringField(
        "権利確定日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='権利確定日はYYYYMMDDで入力してください。'),
        ]
    )

    dividendPaymentDate = StringField(
        "配当支払日",
        validators=[
            Optional(),
            Regexp(yyyymmdd_regexp, message='配当支払日はYYYYMMDDで入力してください。'),
        ]
    )

    cancellationDate = StringField(
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
        choices=[(True, 'True'), (False, 'False')],
        default='True'
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

    abi = TextAreaField("インターフェース", validators=[])
    bytecode = TextAreaField("バイトコード", validators=[])
    submit = SubmitField('設定変更')

    def __init__(self, token_setting=None, *args, **kwargs):
        super(SettingForm, self).__init__(*args, **kwargs)
        self.token_setting = token_setting
        self.transferable.choices = [('True', 'なし'), ('False', 'あり')]

    @staticmethod
    def check_decimal_places(places, field):
        """
        有効小数点桁数チェック
        :param places: 小数点以下有効桁数：整数
        :param field: 桁数チェックを行う変数：小数（Form）
        :return: 真偽値
        """
        float_data = float(field.data * 10 ** places)  # 小数点以下5桁目が存在する場合は小数になる
        int_data = int(field.data * 10 ** places)  # 小数部は切り捨て
        return math.isclose(int_data, float_data)


# 追加発行
class AddSupplyForm(Form):
    token_address = StringField("トークンアドレス", validators=[])
    name = StringField("名称", validators=[])
    total_supply = IntegerField("現在の発行量", validators=[])
    amount = IntegerField(
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


# 所有者移転
class TransferOwnershipForm(Form):
    from_address = StringField("現在の所有者", validators=[])
    to_address = StringField(
        "移転先",
        validators=[
            DataRequired('移転先は必須です。'),
            address('移転先は無効なアドレスです。')
        ]
    )
    amount = IntegerField(
        "移転数量",
        validators=[
            DataRequired('移転数量は必須です。'),
            NumberRange(min=1, max=100_000_000, message='移転数量は100,000,000が上限です。'),
        ]
    )
    submit = SubmitField('移転')

    def __init__(self, transfer_ownership=None, *args, **kwargs):
        super(TransferOwnershipForm, self).__init__(*args, **kwargs)
        self.transfer_ownership = transfer_ownership


# 割当
class TransferForm(Form):
    token_address = StringField(
        "株式アドレス",
        validators=[
            DataRequired('株式アドレスは必須です。')
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
            NumberRange(min=1, max=100_000_000, message='割当数量は100,000,000が上限です。'),
        ]
    )

    submit = SubmitField('割当')

    def __init__(self, transfer_share=None, *args, **kwargs):
        super(TransferForm, self).__init__(*args, **kwargs)
        self.transfer_share = transfer_share


# 募集申込割当
class AllotForm(Form):
    token_address = StringField(
        "株式アドレス",
        validators=[
            DataRequired('株式アドレスは必須です。')
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
