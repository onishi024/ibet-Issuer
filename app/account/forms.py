# -*- coding:utf-8 -*-
from flask_wtf import FlaskForm as Form

from wtforms import StringField, SubmitField, SelectField, PasswordField, FileField
from wtforms.validators import Required, EqualTo, Length, Regexp
from wtforms import ValidationError
from ..models import Role, User
from sqlalchemy import and_

# ベースフォーム
class UserForm(Form):
    login_id = StringField("ログインID", validators=[
        Required('ログインIDは必須です。'),
        Length(min=4, max=12, message='ログインIDは4文字以上12文字までです。'),
        Regexp(r'^[a-z0-9_]+$', message='ログインIDは半角英数アンダースコアのみ使用可能です。'),
    ])
    user_name = StringField("ユーザー名", validators=[Required('ユーザー名は必須です。')])
    icon = FileField("アイコン")
    submit = SubmitField('登録')

    def __init__(self, user=None, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.user = user

    def validate_login_id(self, field):
        chk = None
        if self.user:
            chk = User.query.filter(and_(User.id != self.user.id, User.login_id == field.data)).first()
        else:
            chk = User.query.filter(User.login_id == field.data).first()
        if chk:
            raise ValidationError('このログインIDは既に使用されています。')

# 登録用フォーム
class RegistUserForm(UserForm):
    role = SelectField('ロール', coerce=int)
    def __init__(self, user=None, *args, **kwargs):
        super(RegistUserForm, self).__init__(user, *args, **kwargs)
        self.role.choices = [(role.id, role.name) for role in Role.query.order_by(Role.name).all()]

# 更新用フォーム(管理者)
class EditUserAdminForm(UserForm):
    role = SelectField('ロール', coerce=int)
    def __init__(self, user=None, *args, **kwargs):
        super(EditUserAdminForm, self).__init__(user, *args, **kwargs)
        self.role.choices = [(role.id, role.name) for role in Role.query.order_by(Role.name).all()]

# 更新用フォーム
class EditUserForm(UserForm):
    token = StringField("トークン", validators=[])
    def __init__(self, user, *args, **kwargs):
        super(EditUserForm, self).__init__(user, *args, **kwargs)

# パスワード変更フォーム
class PasswordChangeForm(Form):
    password = PasswordField('新しいパスワード', [ Required('新しいパスワードが入力されていません。'), EqualTo('confirm', message='パスワードが一致しません。') ])
    confirm = PasswordField('新しいパスワード（再入力）')
    submit = SubmitField('変更する')

# 銀行口座情報登録フォーム
class BankInfoForm(Form):
    bank_name = StringField("金融機関名", validators=[
                    Required('金融機関名は必須です。'),
                    Length(max=40, message='金融機関名は40文字までです。')
                    ])
    bank_code = StringField("金融機関コード", validators=[
                    Required('金融機関コードは必須です。'),
                    Length(min=4, max=4, message='金融機関コードは4桁です。'),
                    Regexp(r'^[0-9]+$', message='金融機関コードは数字のみです。')
                    ])
    branch_name = StringField("支店名", validators=[
                    Required('支店名は必須です。'),
                    Length(max=40, message='支店名は40文字までです。')
                    ])
    branch_code = StringField("支店コード", validators=[
                    Required('支店コードは必須です。'),
                    Length(min=3, max=3, message='支店コードは3桁です。'),
                    Regexp(r'^[0-9]+$', message='支店コードは数字のみです。')
                    ])
    account_type = SelectField('口座種別', coerce=str)
    account_number = StringField("口座番号", validators=[
                    Required('口座番号は必須です。'),
                    Length(min=7, max=7, message='口座番号は7桁です。'),
                    Regexp(r'^[0-9]+$', message='口座番号は数字のみです。')
                    ])
    account_holder = StringField("口座名義", validators=[
                    Required('口座名義は必須です。'),
                    Length(max=40, message='口座名義は40文字までです。'),
                    Regexp(r'^[A-Z0-9ｱ-ﾝﾞﾟ\-\(\)\.\/]+$', message='口座名義は半角カナ文字（大文字）、半角英数字、一部の記号のみです。')
                    ])
    submit = SubmitField('登録')

    def __init__(self, bank_info=None, *args, **kwargs):
        super(BankInfoForm, self).__init__(*args, **kwargs)
        self.account_type.choices = [('1', '普通'), ('2', '当座'), ('4', '貯蓄預金'), ('9', 'その他')]
        self.bank_info = bank_info


# 発行体情報登録用フォーム
class IssuerInfoForm(Form):
    issuer_name = StringField('発行体名義', validators=[
        Length(max=64, message='発行体名義は64文字までです。')
    ])
    submit = SubmitField('登録')

    def __init__(self, issuer_info=None, *args, **kwargs):
        super(IssuerInfoForm, self).__init__(*args, **kwargs)
        self.issuer_info = issuer_info
