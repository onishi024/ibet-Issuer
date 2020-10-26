#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

mv ./app/tests/data/rsa/test_private.pem ./data/rsa/private.pem
mv ./app/tests/data/rsa/test_public.pem ./data/rsa/public.pem

sleep 10

# test
python manage.py test -v --cov 

status_code=$?

mv coverage.xml ./cov

if [ $status_code -ne 0 ]; then
  exit 1
fi
