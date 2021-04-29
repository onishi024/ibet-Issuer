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
from datetime import (
    datetime,
    timezone,
    timedelta
)
import json
import logging
from logging.config import dictConfig
import os
import sys
import time

from eth_utils import to_checksum_address
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    sessionmaker,
    scoped_session
)
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import MismatchedABI

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.models import (
    Token,
    Consume
)
from config import Config

dictConfig(Config.LOG_CONFIG)
log_fmt = '[%(asctime)s] [INDEXER-Consume] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(format=log_fmt)

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

JST = timezone(timedelta(hours=+9), "JST")


class Sinks:
    def __init__(self):
        self.sinks = []

    def register(self, sink):
        self.sinks.append(sink)

    def on_consume(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_consume(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_consume(self, transaction_hash, token_address,
                   consumer_address, balance, total_used_amount, used_amount, block_timestamp):
        logging.debug(f"Consume: transaction_hash={transaction_hash}, token_address={token_address}, used_amount={used_amount}")
        consume_record = self.__get_record(transaction_hash, token_address)
        if consume_record is None:
            consume_record = Consume()
            consume_record.transaction_hash = transaction_hash
            consume_record.token_address = token_address
            consume_record.consumer_address = consumer_address
            consume_record.balance = balance
            consume_record.total_used_amount = total_used_amount
            consume_record.used_amount = used_amount
            consume_record.block_timestamp = block_timestamp
            self.db.merge(consume_record)

    def flush(self):
        self.db.commit()

    def __get_record(self, transaction_hash, token_address):
        return self.db.query(Consume). \
            filter(Consume.transaction_hash == transaction_hash). \
            filter(Consume.token_address == token_address). \
            first()


class Processor:
    def __init__(self, sink, db):
        self.sink = sink
        self.latest_block = web3.eth.blockNumber
        self.db = db
        self.token_list = []

    def get_consumable_token_list(self):
        self.token_list = []
        issued_token_list = self.db.query(Token).all()
        for issued_token in issued_token_list:
            if issued_token.token_address is not None:
                abi = json.loads(issued_token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                token_contract = web3.eth.contract(
                    address=issued_token.token_address,
                    abi=abi
                )
                # Consumeイベントを発生させるトークンのみを追加
                try:
                    if token_contract.events.Consume is not None:
                        self.token_list.append(token_contract)
                except MismatchedABI:
                    # Consumeイベントを発生させないトークンの場合、スキップ
                    pass

    def initial_sync(self):
        self.get_consumable_token_list()
        # 1,000,000ブロックずつ同期処理を行う
        _to_block = 999999
        _from_block = 0
        if self.latest_block > 999999:
            while _to_block < self.latest_block:
                self.__sync_all(_from_block, _to_block)
                _to_block += 1000000
                _from_block += 1000000
            self.__sync_all(_from_block, self.latest_block)
        else:
            self.__sync_all(_from_block, self.latest_block)

    def sync_new_logs(self):
        self.get_consumable_token_list()
        blockTo = web3.eth.blockNumber
        if blockTo <= self.latest_block:
            return
        self.__sync_all(self.latest_block + 1, blockTo)
        self.latest_block = blockTo

    def __sync_all(self, block_from, block_to):
        logging.info("syncing from={}, to={}".format(block_from, block_to))
        self.__sync_consume(block_from, block_to)
        self.sink.flush()

    def __sync_consume(self, block_from, block_to):
        for token in self.token_list:
            try:
                events = token.events.Consume.getLogs(
                    fromBlock=block_from,
                    toBlock=block_to
                )
                for event in events:
                    args = event['args']
                    transaction_hash = event['transactionHash'].hex()
                    block_timestamp = datetime.fromtimestamp(web3.eth.getBlock(event['blockNumber'])['timestamp'], JST)
                    # オーバーフロー対策
                    if args['balance'] > sys.maxsize or args['used'] > sys.maxsize or args['value'] > sys.maxsize:
                        pass
                    else:
                        self.sink.on_consume(
                            transaction_hash=transaction_hash,
                            token_address=to_checksum_address(token.address),
                            consumer_address=args['consumer'],
                            balance=args['balance'],
                            total_used_amount=args['used'],
                            used_amount=args['value'],
                            block_timestamp=block_timestamp
                        )
            except Exception as e:
                logging.error(e)


_sink = Sinks()
_sink.register(DBSink(db_session))
processor = Processor(sink=_sink, db=db_session)
logging.info("Service started successfully")

processor.initial_sync()
while True:
    processor.sync_new_logs()
    time.sleep(Config.INTERVAL_INDEXER_CONSUME)
