# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.util import eth_unlock_account
from app.contracts import Contract
from app.models import CouponBulkTransfer, Token
from config import Config

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
log_fmt = 'PROCESSOR-BatchTransferCoupon [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt)

# 設定情報の取得
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
URI = os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
exchange_address = Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS

# 初期化
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

# Exchangeコントラクトへの接続
exchange_contract = Contract.get_contract('IbetCouponExchange', exchange_address)

# 常時起動（無限ループ）
while True:
    logging.info('[CouponBatchTransfer] Loop Start')

    # 割当（Transfer）済ではないレコードを抽出
    try:
        untransferred_list = db_session.query(CouponBulkTransfer). \
            filter(CouponBulkTransfer.transferred == False).all()
    except Exception as err:
        logging.error("%s", err)
        time.sleep(10)
        continue

    # レコード単位で割当処理を実行
    for item in untransferred_list:

        # Tokenコントラクトへの接続
        token = db_session.query(Token).filter(Token.token_address == item.token_address).first()
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        TokenContract = web3.eth.contract(
            address=token.token_address,
            abi=token_abi
        )

        # 割当処理
        from_address = Config.ETH_ACCOUNT # 発行体アドレス
        to_address = to_checksum_address(item.to_address)
        amount = item.amount

        try:
            # EOAのアンロック
            eth_unlock_account()

            # 取引所コントラクトへデポジット（Transfer）
            deposit_gas = TokenContract.estimateGas(). \
                transferFrom(from_address, exchange_address, amount)
            TokenContract.functions. \
                transferFrom(from_address, exchange_address, amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': deposit_gas})

            # 取引所コントラクトから割当先へTransfer
            transfer_gas = exchange_contract.estimateGas(). \
                transfer(to_checksum_address(TokenContract.address), to_address, amount)
            exchange_contract.functions. \
                transfer(to_checksum_address(TokenContract.address), to_address, amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': transfer_gas})

            # DBを割当済に更新
            item.transferred = True

            logging.info("[CouponBatchTransfer] Success : {}".format(item.token_address))

        except Exception as err:
            logging.error("%s", err)
            break

        db_session.commit()

    logging.info('[CouponBatchTransfer] Loop Finished')
    time.sleep(3)
