#!/bin/bash
source ~/.bash_profile

cd /app/tmr-issuer

#run server
python rsa/create_rsakey.py $1
