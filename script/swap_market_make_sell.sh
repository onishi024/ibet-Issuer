#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

# script
python script/swap_market_make_sell.py $DEPOSIT_AMOUNT_DR
