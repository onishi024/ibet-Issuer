# -*- coding: utf-8 -*-
import sys
import os
import time
import sqlalchemy as sa
from web3 import Web3

WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER') or 'http://localhost:8545'
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

URI = os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = sa.create_engine(URI, echo=False)

import logging
# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
log_fmt = 'PROCESSOR-IssueEvent [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_fmt)

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
        except:
            continue

        if tx_receipt is not None :
            # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
            if 'contractAddress' in tx_receipt.keys():
                admin_address = tx_receipt['from']
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
