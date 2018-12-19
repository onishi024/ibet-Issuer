#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

# test
python manage.py test -v --cov 
