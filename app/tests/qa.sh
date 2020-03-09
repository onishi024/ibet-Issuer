#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

# test
python manage.py test -v --cov 
