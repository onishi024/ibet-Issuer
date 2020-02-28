# -*- coding: utf-8 -*-
import json
import os
import sys
import time
import logging
from logging.config import dictConfig

from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=+9), "JST")

from eth_utils import to_checksum_address
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.models import Token, Transfer
from config import Config

from web3 import Web3
from web3.middleware import geth_poa_middleware

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
dictConfig(Config.LOG_CONFIG)
log_fmt = 'INDEXER-Transfer [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(format=log_fmt)

# 設定の取得
WEB3_HTTP_PROVIDER = Config.WEB3_HTTP_PROVIDER
URI = Config.SQLALCHEMY_DATABASE_URI

# 初期化
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)


class Sinks:
    def __init__(self):
        self.sinks = []

    def register(self, sink):
        self.sinks.append(sink)

    def on_transfer(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_transfer(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class ConsoleSink:
    @staticmethod
    def on_transfer(transaction_hash, token_address,
                    account_address_from, account_address_to, transfer_amount, block_timestamp):
        logging.info(
            "Transfer: transaction_hash={}, token_address={}, account_address_from={}, account_address_to={}".format(
                transaction_hash, token_address, account_address_from, account_address_to
            )
        )

    def flush(self):
        return


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_transfer(self, transaction_hash, token_address,
                    account_address_from, account_address_to, transfer_amount, block_timestamp):
        transfer_record = self.__get_record(transaction_hash, token_address)
        if transfer_record is None:
            transfer_record = Transfer()
            transfer_record.transaction_hash = transaction_hash
            transfer_record.token_address = token_address
            transfer_record.account_address_from = account_address_from
            transfer_record.account_address_to = account_address_to
            transfer_record.transfer_amount = transfer_amount
            transfer_record.block_timestamp = block_timestamp
            self.db.merge(transfer_record)

    def flush(self):
        self.db.commit()

    def __get_record(self, transaction_hash, token_address):
        return self.db.query(Transfer). \
            filter(Transfer.transaction_hash == transaction_hash). \
            filter(Transfer.token_address == token_address). \
            first()


class Processor:
    def __init__(self, web3, sink, db):
        self.web3 = web3
        self.sink = sink
        self.latest_block = web3.eth.blockNumber
        self.db = db
        self.token_list = []

    def get_token_list(self):
        self.token_list = []
        issued_token_list = self.db.query(Token).all()
        for issued_token in issued_token_list:
            if issued_token.token_address is not None:
                abi = json.loads(issued_token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                token_contract = web3.eth.contract(
                    address=issued_token.token_address,
                    abi=abi
                )
                self.token_list.append(token_contract)

    def initial_sync(self):
        self.get_token_list()
        self.__sync_all(0, self.latest_block)

    def sync_new_logs(self):
        self.get_token_list()
        blockTo = web3.eth.blockNumber
        if blockTo == self.latest_block:
            return
        self.__sync_all(self.latest_block + 1, blockTo)
        self.latest_block = blockTo

    def __sync_all(self, block_from, block_to):
        logging.debug("syncing from={}, to={}".format(block_from, block_to))
        self.__sync_transfer(block_from, block_to)
        self.sink.flush()

    def __sync_transfer(self, block_from, block_to):
        for token in self.token_list:
            try:
                event_filter = token.eventFilter(
                    'Transfer', {
                        'fromBlock': block_from,
                        'toBlock': block_to,
                    }
                )
                for event in event_filter.get_all_entries():
                    args = event['args']
                    transaction_hash = event['transactionHash'].hex()
                    block_timestamp = datetime.fromtimestamp(web3.eth.getBlock(event['blockNumber'])['timestamp'], JST)
                    if args['value'] > sys.maxsize:
                        pass
                    else:
                        self.sink.on_transfer(
                            transaction_hash=transaction_hash,
                            token_address=to_checksum_address(token.address),
                            account_address_from=args['from'],
                            account_address_to=args['to'],
                            transfer_amount=args['value'],
                            block_timestamp=block_timestamp
                        )
                self.web3.eth.uninstallFilter(event_filter.filter_id)
            except Exception as e:
                logging.error(e)
                pass


sink = Sinks()
sink.register(ConsoleSink())
sink.register(DBSink(db_session))
processor = Processor(web3, sink, db_session)

processor.initial_sync()
while True:
    processor.sync_new_logs()
    time.sleep(10)
