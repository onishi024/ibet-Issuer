#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

# script
python script/swap_market_make_buy.py < /dev/null 2>&1 /dev/null &
python script/swap_market_make_sell.py < /dev/null 2>&1 /dev/null &
