#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

# async
nohup python async/processor_IssueEvent.py < /dev/null 2>&1 /dev/null &
nohup python async/processor_BatchTransfer_coupon.py < /dev/null 2>&1 /dev/null &
nohup python async/processor_BatchTransfer_mrf.py < /dev/null 2>&1 /dev/null &

#run server
gunicorn -b 0.0.0.0:5000 --reload manage:app --config guniconf.py
