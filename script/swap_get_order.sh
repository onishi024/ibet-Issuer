#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

# script
python script/swap_get_order.py $1 $2