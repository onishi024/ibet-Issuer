#!/bin/bash
source ~/.bash_profile

cd /app/ibet-Issuer

#run server
python rsa/create_rsakey.py $1

chmod 444 data/rsa/private.pem
chmod 444 data/rsa/public.pem
