#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

# script
python script/swap_withdraw_all.py $1 $2
