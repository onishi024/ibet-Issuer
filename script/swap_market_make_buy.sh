#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

# script
python script/swap_market_make_buy.py $DEPOSIT_AMOUNT_MRF
