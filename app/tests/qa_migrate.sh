#!/bin/bash
set -Ceu

source ~/.bash_profile
cd /app/tmr-issuer

python manage.py db init
python manage.py db migrate
python manage.py db upgrade
python manage.py shell <<END
roles = ['admin', 'user',]
for r in roles:
    role = Role.query.filter_by(name=r).first()
    if role is None:
        role = Role(name=r)
    db.session.add(role)

users = [
     {'login_id': 'admin', 'user_name': '管理者', 'role_id': 1, 'password': 'admin'},
]

for u_dict in users:
    user = User.query.filter_by(login_id=u_dict['login_id']).first()
    if user is None:
        user = User()
        for key, value in u_dict.items():
            setattr(user, key, value)
        db.session.add(user)

db.session.commit()
END
