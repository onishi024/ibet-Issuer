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
from app.models import MRFBulkTransfer, Token
from config import Config

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
log_fmt = 'PROCESSOR [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt)

# 設定情報の取得
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
URI = os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'

# 初期化
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

# 常時起動（無限ループ）
while True:
    logging.info('[MRFBatchTransfer] Loop Start')

    # 割当（Transfer）済ではないレコードを抽出
    try:
        untransfered_list = db_session.query(MRFBulkTransfer). \
            filter(MRFBulkTransfer.transferred == False).all()
    except Exception as err:
        logging.error("%s", err)
        break

    # レコード単位で割当処理を実行
    for item in untransfered_list:

        # Tokenコントラクトへの接続
        token = db_session.query(Token).filter(Token.token_address == item.token_address).first()
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        TokenContract = web3.eth.contract(
            address=token.token_address,
            abi=token_abi
        )

        # 割当処理
        to_address = to_checksum_address(item.to_address)
        amount = item.amount

        try:
            # EOAのアンロック
            eth_unlock_account()

            # Transfer
            transfer_gas = TokenContract.estimateGas().transfer(to_address, amount)
            TokenContract.functions.transfer(to_address, amount). \
                transact({'from': Config.ETH_ACCOUNT, 'gas': transfer_gas})

            # DBを割当済に更新
            item.transferred = True

            logging.info("[MRFBatchTransfer] Success : {}".format(item.token_address))

        except Exception as err:
            logging.error("%s", err)
            break

        db_session.commit()

    logging.info('[MRFBatchTransfer] Loop Finished')
    time.sleep(3)
