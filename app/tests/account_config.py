# -*- coding: utf-8 -*-
from web3 import Web3
from config import Config

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))

# Account Address
eth_account = {
    'agent': {
        'account_address': web3.eth.accounts[0],
        'password': 'password'
    },
    'issuer': {
        'account_address': web3.eth.accounts[1],
        'password': 'password'
    },
    'deployer': {
        'account_address': web3.eth.accounts[2],
        'password': 'password'
    },
    'trader': {
        'account_address': web3.eth.accounts[3],
        'password': 'password'
    }
}
