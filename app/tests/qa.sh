#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

mv ./app/tests/data/rsa/test_private.pem ./data/rsa/private.pem
mv ./app/tests/data/rsa/test_public.pem ./data/rsa/public.pem

sleep 10

# test
python manage.py test -v --cov 

mv coverage.xml ./cov