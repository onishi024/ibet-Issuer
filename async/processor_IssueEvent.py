# -*- coding: utf-8 -*-
import os
import time
import sqlalchemy as sa
from web3 import Web3

web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))

URI = os.environ.get('DATABASE_URL') or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = sa.create_engine(URI, echo=False)

while True:

    # コントラクトアドレスが登録されていないTokenの一覧を抽出
    token_unprocessed = engine.execute(
        "select * from tokens where token_address IS NULL"
    )

    for row in token_unprocessed:
        tx_hash = row['tx_hash']
        tx_hash_hex = '0x' + tx_hash[2:]
        tx_receipt = web3.eth.getTransactionReceipt(tx_hash_hex)
        if tx_receipt is not None :
            # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
            if 'contractAddress' in tx_receipt.keys():
                admin_address = tx_receipt['from']
                contract_address = tx_receipt['contractAddress']

                # 登録済みトークン情報に発行者のアドレスと、トークンアドレスの登録を行う。
                query_tokens = "update tokens " + \
                    "set admin_address = \'" + admin_address + "\' , " + \
                    "token_address = \'" + contract_address + "\' " + \
                    "where tx_hash = \'" + tx_hash + "\'"
                engine.execute(query_tokens)

                print("issued --> " + contract_address)

    time.sleep(10)
