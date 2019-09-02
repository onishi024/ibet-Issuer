# -*- coding: utf-8 -*-
import argparse
import os
import sys

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

path = os.path.join(os.path.dirname(__file__), "../")
sys.path.append(path)
from app.contracts import Contract

# Web3設定
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

ETH_ACCOUNT = os.environ.get('ETH_ACCOUNT') or web3.eth.accounts[0]
ETH_ACCOUNT = to_checksum_address(ETH_ACCOUNT)
ETH_ACCOUNT_PASSWORD = os.environ.get('ETH_ACCOUNT_PASSWORD')


def deposit(dr_token_address, mrf_token_address, swap_contract_address, is_buy, amount, price):
    """
    SWAPコントラクトへのデポジット
    """
    if is_buy is True:
        TokenContract = Contract.get_contract('IbetMRF', mrf_token_address)
        transfer_amount = int(amount) * int(price)
        gas = TokenContract.estimateGas(). \
            transfer(swap_contract_address, transfer_amount)
        tx_hash = TokenContract.functions. \
            transfer(swap_contract_address, transfer_amount). \
            transact({'from': ETH_ACCOUNT, 'gas': gas})
    else:
        TokenContract = Contract.get_contract('IbetDepositaryReceipt', dr_token_address)
        gas = TokenContract.estimateGas(). \
            transfer(swap_contract_address, amount)
        tx_hash = TokenContract.functions. \
            transfer(swap_contract_address, amount). \
            transact({'from': ETH_ACCOUNT, 'gas': gas})

    web3.eth.waitForTransactionReceipt(tx_hash)
    print('transfer executed successfully')


def make_order(dr_token_address, mrf_token_address, swap_contract_address, is_buy, amount, price):
    """
    Make注文
    """
    SwapContract = Contract.get_contract('IbetSwap', swap_contract_address)
    gas = SwapContract.estimateGas(). \
        makeOrder(dr_token_address, amount, price, is_buy)
    tx_hash = SwapContract.functions. \
        makeOrder(dr_token_address, amount, price, is_buy). \
        transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)
    print('makeOrder executed successfully')


def main(dr_token_address, mrf_token_address, swap_contract_address, is_buy, amount, price):
    """
    Main処理
    """
    dr_token_address = to_checksum_address(dr_token_address)
    mrf_token_address = to_checksum_address(mrf_token_address)
    swap_contract_address = to_checksum_address(swap_contract_address)

    if is_buy == "True":
        is_buy = True
    else:
        is_buy = False

    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    # SWAPコントラクトへデポジット
    deposit(dr_token_address, mrf_token_address, swap_contract_address, is_buy, amount, price)

    # Make注文
    make_order(dr_token_address, mrf_token_address, swap_contract_address, is_buy, amount, price)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWAPコントラクトへのMake注文の作成")
    parser.add_argument("dr_token_address", type=str, help="DepositaryReceiptトークンアドレス")
    parser.add_argument("mrf_token_address", type=str, help="MRFトークンアドレス")
    parser.add_argument("swap_contract_address", type=str, help="SWAPコントラクトアドレス")
    parser.add_argument("is_buy", type=bool, help="売買区分")
    parser.add_argument("amount", type=int, help="注文数量")
    parser.add_argument("price", type=int, help="注文単価")
    args = parser.parse_args()

    main(args.dr_token_address, args.mrf_token_address, args.swap_contract_address,
         args.is_buy, args.amount, args.price)
