from flask_wtf import FlaskForm as Form
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired

class LoginForm(Form):
    login_id = StringField("LoginId", validators=[DataRequired("ログインIDを入力してください。")])
    password = PasswordField("Password", validators=[DataRequired("パスワードを入力してください。")])

    class Meta:
        csrf = False

