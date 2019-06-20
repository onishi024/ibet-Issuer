# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from web3 import Web3
from eth_utils import to_checksum_address

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.util import eth_unlock_account
from app.contracts import Contract
from app.models import CSVTransfer, Token
from config import Config

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
log_fmt = 'PROCESSOR [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt)


"""
CSVアップロードされた割当情報から、Transferコントラクトを実行する
"""
# 設定情報の読み込み
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
URI = os.environ.get('DATABASE_URL') or 'postgresql://bsuser:bspass@localhost:5432/bsdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS


def transfer_token(TokenContract, from_address, to_address, amount):
    eth_unlock_account()
    token_exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS
    ExchangeContract = Contract.get_contract(
        'IbetCouponExchange', token_exchange_address)

    # 取引所コントラクトへトークン送信
    deposit_gas = TokenContract.estimateGas(). \
        transferFrom(from_address, token_exchange_address, amount)
    TokenContract.functions. \
        transferFrom(from_address, token_exchange_address, amount). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})

    # 取引所コントラクトからtransferで送信相手へ送信
    transfer_gas = ExchangeContract.estimateGas(). \
        transfer(to_checksum_address(TokenContract.address), to_address, amount)
    tx_hash = ExchangeContract.functions. \
        transfer(to_checksum_address(TokenContract.address), to_address, amount). \
        transact({'from': Config.ETH_ACCOUNT, 'gas': transfer_gas})
    return tx_hash


# 常時起動（無限ループ）
while True:

    logging.info('start batch')
    # Issue済ではない一覧を抽出
    try:
        untransferred_list = db_session.query(CSVTransfer). \
            filter(CSVTransfer.transferred == False).all()
    except Exception as err:
        logging.error("%s", err)
        break

    # EOAのアンロック
    eth_unlock_account()
    logging.info('eth_unlock_account() called')

    for item in untransferred_list:
        logging.info('starting for roop')
        # Tokenコントラクト接続
        try:
            token = Token.query.filter(Token.token_address == item.coupon_address).first()
            token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
            TokenContract = web3.eth.contract(
                address=token.coupon_address,
                abi=token_abi
            )
            logging.info('connected to Token Contract')

            # 割当処理（発行体アドレス→指定アドレス）
            from_address = Config.ETH_ACCOUNT
            to_address = to_checksum_address(item.to_address)
            amount = item.amount
            tx_hash = transfer_token(TokenContract, from_address, to_address, amount)
            logging.info('Token Transferred')

            # 発行済状態に更新
            try:
                item.transferred = True
                logging.info("The coupon was transferred. : {}".format(item.coupon_address))
            except Exception as err:
                logging.error("%s", err)
                break
            logging.info('db updated')

            db_session.commit()

        except Exception as e:
            logging.error(e)



    time.sleep(3)
