# -*- coding: utf-8 -*-
import os
import sys
import time
import logging
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

path = os.path.join(os.path.dirname(__file__), "../")
sys.path.append(path)

from app.contracts import Contract
from app.models import SwapMarketMakeOrder

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
log_fmt = 'PROCESSOR [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt)

# Sleep間隔（10分間隔）
SLEEP_INTERVAL = int(600)

# Web3設定
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

ETH_ACCOUNT = os.environ.get('ETH_ACCOUNT') or web3.eth.accounts[0]
ETH_ACCOUNT = to_checksum_address(ETH_ACCOUNT)
ETH_ACCOUNT_PASSWORD = os.environ.get('ETH_ACCOUNT_PASSWORD')

# DB設定
URI = os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)


def deposit(settlement_token_address, swap_address, deposit_amount_mrf):
    """
    SWAPコントラクトへのデポジット
    """
    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    TokenContract = Contract.get_contract('IbetMRF', settlement_token_address)
    balance = TokenContract.functions.balanceOf(ETH_ACCOUNT).call()

    if deposit_amount_mrf > balance:
        gas = TokenContract.estimateGas().transfer(swap_address, balance)
        tx_hash = TokenContract.functions.transfer(swap_address, balance). \
            transact({'from': ETH_ACCOUNT, 'gas': gas})
    else:
        gas = TokenContract.estimateGas().transfer(swap_address, deposit_amount_mrf)
        tx_hash = TokenContract.functions.transfer(swap_address, deposit_amount_mrf). \
            transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)


def make_order(token_address, swap_address, amount, price):
    """
    Make注文
    """
    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    SwapContract = Contract.get_contract('IbetSwap', swap_address)
    gas = SwapContract.estimateGas().makeOrder(token_address, amount, price, True)
    tx_hash = SwapContract.functions.makeOrder(token_address, amount, price, True). \
        transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)

    order_id = SwapContract.functions.latestOrderId().call()
    return order_id


def init_order(token_address, settlement_token_address, swap_address, amount, price, deposit_amount_mrf):
    """
    新規注文
    """
    # SWAPコントラクトにSettlementTokenの残高をデポジット
    deposit(settlement_token_address, swap_address, deposit_amount_mrf)
    # Make注文
    order_id = make_order(token_address, swap_address, amount, price)

    return order_id


def change_order(swap_address, order_id, amount, price):
    """
    注文訂正
    """
    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    SwapContract = Contract.get_contract('IbetSwap', swap_address)
    gas = SwapContract.estimateGas().changeOrder(order_id, amount, price)
    tx_hash = SwapContract.functions.changeOrder(order_id, amount, price). \
        transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)


def cancel_order(swap_address, order_id):
    """
    注文キャンセル
    """
    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    SwapContract = Contract.get_contract('IbetSwap', swap_address)
    gas = SwapContract.estimateGas().cancelOrder(order_id)
    tx_hash = SwapContract.functions.cancelOrder(order_id). \
        transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)


def withdraw(swap_address, settlement_token_address):
    """
    引き出し
    """
    # アカウントアンロック
    web3.personal.unlockAccount(ETH_ACCOUNT, ETH_ACCOUNT_PASSWORD, 1000)

    SwapContract = Contract.get_contract('IbetSwap', swap_address)
    gas = SwapContract.estimateGas().withdrawAll(settlement_token_address)
    tx_hash = SwapContract.functions.withdrawAll(settlement_token_address). \
        transact({'from': ETH_ACCOUNT, 'gas': gas})
    web3.eth.waitForTransactionReceipt(tx_hash)


def main(deposit_amount_mrf):
    """
    Main処理
    """

    # 未発注レコードを抽出
    order_list = []
    try:
        order_list = db_session.query(SwapMarketMakeOrder). \
            filter(SwapMarketMakeOrder.ordered == False). \
            filter(SwapMarketMakeOrder.is_buy == True). \
            all()
    except Exception as err:
        logging.error("%s", err)

    logging.info('[SwapMarketMake_Buy] Loop Start')

    init_flg = True
    order_id = 0
    swap_address = '0x0000000000000000000000000000000000000000'
    settlement_token_address = '0x0000000000000000000000000000000000000000'
    for order in order_list:
        start_time = time.time()
        token_address = to_checksum_address(order.token_address)
        settlement_token_address = to_checksum_address(order.settlement_token_address)
        swap_address = to_checksum_address(order.swap_address)

        if init_flg is True:
            order_id = init_order(token_address, settlement_token_address, swap_address,
                                  order.amount, order.price, deposit_amount_mrf)
            logging.info("[SwapMarketMake_Buy] OrderID - {}".format(order_id))
        else:
            change_order(swap_address, order_id, order.amount, order.price)

        # 注文済に更新
        order.ordered = True
        db_session.commit()

        elapsed_time = time.time() - start_time
        init_flg = False

        logging.info("[SwapMarketMake_Buy] Order Finished in {} secs".format(elapsed_time))
        time.sleep(max(SLEEP_INTERVAL - elapsed_time, 0))

    logging.info('[SwapMarketMake_Buy] Loop Finished')

    if init_flg is False:
        cancel_order(swap_address, order_id)
        withdraw(swap_address, settlement_token_address)
        logging.info('[SwapMarketMake_Buy] Order Canceled')


if __name__ == "__main__":
    if sys.argv:
        del sys.argv[1:]

    parser = argparse.ArgumentParser(description="MarketMake用BOT（BUY）")
    parser.add_argument("deposit_amount_mrf", type=int, help="MRFトークンのデポジット数量")
    args = parser.parse_args()

    main(args.deposit_amount_mrf)
