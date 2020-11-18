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

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.utils import ContractUtils
from app.models import BulkTransfer, Token
from config import Config

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
dictConfig(Config.LOG_CONFIG)
log_fmt = 'PROCESSOR-BatchTransfer [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
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
    logging.debug('Loop Start')

    # 実行承認済、かつ未実行のレコードリストを抽出
    transfer_list = db_session.query(BulkTransfer).\
        filter(BulkTransfer.approved == True).\
        filter(BulkTransfer.status == 0).\
        all()

    # レコード単位で移転処理を実行
    for record in transfer_list:
        # Tokenコントラクトに接続
        token = db_session.query(Token). \
            filter(Token.token_address == record.token_address). \
            filter(Token.admin_address == record.eth_account.lower()). \
            first()
        if token is None:
            logging.warning('Cannot handle coupon token address %s', record.token_address)
            continue
        token_abi = json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
        TokenContract = web3.eth.contract(
            address=token.token_address,
            abi=token_abi
        )
        # 強制移転処理
        from_address = record.from_address
        to_address = record.to_address
        amount = record.amount
        try:
            tx = TokenContract.functions.transferFrom(from_address, to_address, amount). \
                buildTransaction({'from': record.eth_account, 'gas': Config.TX_GAS_LIMIT})
            tx_hash, txn_receipt = ContractUtils.send_transaction(
                transaction=tx,
                eth_account=record.eth_account,
                db_session=db_session
            )
            # エラー判定
            if txn_receipt["status"] == 1:  # トランザクションが正常終了
                record.status = 1  # 正常終了
                logging.info(f"Transfer was successful: eth_account={record.eth_account}, "
                             f"upload_id={record.upload_id}, id={record.id}")
            else:
                record.status = 2  # 異常終了
                logging.error(f"Transfer was failed: eth_account={record.eth_account}, "
                              f"upload_id={record.upload_id}, id={record.id}")
        except Exception as err:
            record.status = 2  # 異常終了
            logging.error(f"Transfer was failed: eth_account={record.eth_account}, "
                          f"upload_id={record.upload_id}, id={record.id} : {err}")

        # 更新情報をコミット
        db_session.commit()

    logging.debug('Loop Finished')
    time.sleep(10)
