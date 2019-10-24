#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

# script
python script/swap_cancel_order.py $1 $2
