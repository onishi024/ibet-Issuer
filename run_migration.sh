#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

python manage.py resetdb
python manage.py db init
python manage.py db migrate
python manage.py db upgrade
