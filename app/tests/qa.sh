#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

# test
python manage.py test -v --cov 

# カバレッジファイルの移動
mv coverage.xml cov/