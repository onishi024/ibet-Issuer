from flask_wtf import FlaskForm as Form

from wtforms import StringField, TextAreaField, PasswordField, SubmitField, HiddenField, SelectField, PasswordField, FileField
from wtforms.validators import Required, Email, EqualTo, Length, Regexp
from wtforms import ValidationError
from ..models import Role, User
from sqlalchemy import or_, and_

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
