# -*- coding: utf-8 -*-
import sys
import os
import json
import time
import logging
from logging.config import dictConfig

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.utils import ContractUtils
from app.models import CouponBulkTransfer, Token
from config import Config

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
dictConfig(Config.LOG_CONFIG)
log_fmt = 'PROCESSOR-BatchTransferCoupon [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(format=log_fmt)

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
exchange_contract = ContractUtils.get_contract('IbetCouponExchange', exchange_address)

# 常時起動（無限ループ）
while True:
    logging.debug('[CouponBatchTransfer] Loop Start')

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
        from_address = Config.ETH_ACCOUNT  # 発行体アドレス
        to_address = to_checksum_address(item.to_address)
        amount = item.amount

        try:
            # DEXコントラクトへデポジット（Transfer）
            gas = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                estimateGas({'from': Config.ETH_ACCOUNT})
            tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                buildTransaction({'from': Config.ETH_ACCOUNT, 'gas': gas})
            ContractUtils.send_transaction(transaction=tx)

            # DBを割当済に更新
            item.transferred = True

            logging.info("[CouponBatchTransfer] Success : {}".format(item.token_address))

        except Exception as err:
            logging.error("%s", err)
            break

        db_session.commit()

    logging.debug('[CouponBatchTransfer] Loop Finished')
    time.sleep(10)
