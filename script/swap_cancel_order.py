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


def cancel_order(swap_contract_address, order_id):
    """
    Cancel注文
    """
    SwapContract = Contract.get_contract('IbetSwap', swap_contract_address)
    gas = SwapContract.estimateGas().cancelOrder(order_id)
    tx_hash = SwapContract.functions.cancelOrder(order_id). \
        transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)


def main(swap_contract_address, order_id):
    """
    Main処理
    """
    swap_contract_address = to_checksum_address(swap_contract_address)

    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    # Cancel注文
    cancel_order(swap_contract_address, order_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SWAPコントラクトへのCancel注文")
    parser.add_argument("swap_contract_address", type=str, help="SWAPコントラクトアドレス")
    parser.add_argument("order_id", type=int, help="注文ID")
    args = parser.parse_args()

    main(args.swap_contract_address, args.order_id)