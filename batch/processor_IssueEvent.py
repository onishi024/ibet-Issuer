"""
Copyright BOOSTRY Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""
import logging
from logging.config import dictConfig
import os
import sys
import time

from sqlalchemy import create_engine
from web3 import Web3

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from config import Config

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)

dictConfig(Config.LOG_CONFIG)
log_fmt = '[%(asctime)s] [PROCESSOR-IssueEvent] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(format=log_fmt)


while True:
    # コントラクトアドレスが登録されていないTokenの一覧を抽出
    try:
        token_unprocessed = engine.execute(
            "select * from tokens where token_address IS NULL"
        )
    except Exception as err:
        logging.error("%s", err)
        time.sleep(10)
        continue

    for row in token_unprocessed:
        tx_hash = row['tx_hash']
        tx_hash_hex = '0x' + tx_hash[2:]

        try:
            tx_receipt = web3.eth.getTransactionReceipt(tx_hash_hex)
        except Exception as err:
            logging.exception(err)
            continue

        if tx_receipt is not None:
            # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
            if 'contractAddress' in tx_receipt.keys():
                admin_address = tx_receipt['from'].lower()
                contract_address = tx_receipt['contractAddress']

                # 登録済みトークン情報に発行者のアドレスと、トークンアドレスの登録を行う。
                try:
                    query_tokens = "update tokens " + \
                        "set admin_address = \'" + admin_address + "\' , " + \
                        "token_address = \'" + contract_address + "\' " + \
                        "where tx_hash = \'" + tx_hash + "\'"
                    engine.execute(query_tokens)
                except Exception as err:
                    logging.error("%s", err)
                    break

                logging.info("issued --> " + contract_address)

    time.sleep(10)
