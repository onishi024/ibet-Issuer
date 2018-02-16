from flask_wtf import FlaskForm as Form
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SubmitField, PasswordField
from wtforms.validators import Required, Length, Email, Regexp, DataRequired

class LoginForm(Form):
    login_id = StringField("LoginId", validators=[Required("ログインIDを入力してください。")])
    password = PasswordField("Password", validators=[Required("パスワードを入力してください。")])

    class Meta:
        csrf = False

