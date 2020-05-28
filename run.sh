#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

# async
python async/processor_IssueEvent.py &
python async/processor_BatchTransfer_coupon.py &
python async/processor_Order.py &
python async/processor_Agreement.py &
python async/indexer_Transfer.py &
python async/indexer_ApplyFor.py &
python async/indexer_Consume.py &

#run server
gunicorn -b 0.0.0.0:5000 --reload manage:app --config guniconf.py
