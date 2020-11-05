"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed onan "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""

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

# 初期化
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)


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
        token = db_session.query(Token). \
            filter(Token.token_address == item.token_address). \
            filter(Token.admin_address == item.eth_account.lower()). \
            first()
        if token is None:
            logging.warning('Cannot handle coupon token address %s', item.token_address)
            continue
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        TokenContract = web3.eth.contract(
            address=token.token_address,
            abi=token_abi
        )

        # 割当処理
        from_address = item.eth_account  # 発行体アドレス
        to_address = to_checksum_address(item.to_address)
        amount = item.amount

        try:
            # DEXコントラクトへデポジット（Transfer）
            tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                buildTransaction({'from': item.eth_account, 'gas': Config.TX_GAS_LIMIT})
            ContractUtils.send_transaction(transaction=tx, eth_account=item.eth_account, db_session=db_session)

            # DBを割当済に更新
            item.transferred = True

            logging.info("[CouponBatchTransfer] Success : {}".format(item.token_address))

        except Exception as err:
            logging.error("%s", err)
            break

        db_session.commit()

    logging.debug('[CouponBatchTransfer] Loop Finished')
    time.sleep(10)
