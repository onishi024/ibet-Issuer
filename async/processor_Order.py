# -*- coding: utf-8 -*-
import os
import sys
import time
import logging
from logging.config import dictConfig

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from web3 import Web3
from app.models import Token, Order
from app.contracts import Contract
from config import Config
from web3.middleware import geth_poa_middleware

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
dictConfig(Config.LOG_CONFIG)
log_fmt = 'PROCESSOR-Order [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
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

    def on_new_order(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_new_order(*args, **kwargs)

    def on_cancel_order(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_cancel_order(*args, **kwargs)

    def on_agree(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_agree(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class ConsoleSink:
    @staticmethod
    def on_new_order(token_address, exchange_address,
                     order_id, account_address, is_buy, price, amount, agent_address):
        logging.info(
            "NewOrder: exchange_address={}, order_id={}".format(
                exchange_address, order_id
            )
        )

    @staticmethod
    def on_cancel_order(exchange_address, order_id):
        logging.info(
            "CancelOrder: exchange_address={}, order_id={}".format(
                exchange_address, order_id
            )
        )

    @staticmethod
    def on_agree(exchange_address, order_id, order_amount):
        logging.info(
            "Agree: exchange_address={}, orderId={}".format(
                exchange_address, order_id
            )
        )

    def flush(self):
        return


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_new_order(self, token_address, exchange_address, order_id, account_address,
                     is_buy, price, amount, agent_address):
        order = self.__get_order(exchange_address, order_id)
        if order is None:
            order = Order()
            order.token_address = token_address
            order.exchange_address = exchange_address
            order.order_id = order_id
            order.unique_order_id = exchange_address + '_' + str(order_id)
            order.account_address = account_address
            order.is_buy = is_buy
            order.price = price
            order.amount = amount
            order.agent_address = agent_address
            order.is_cancelled = False
            self.db.merge(order)

    def on_cancel_order(self, exchange_address, order_id):
        order = self.__get_order(exchange_address, order_id)
        if order is not None:
            order.is_cancelled = True

    def on_agree(self, exchange_address, order_id, order_amount):
        order = self.__get_order(exchange_address, order_id)
        if order is not None:
            order.amount = order_amount

    def flush(self):
        self.db.commit()

    def __get_order(self, exchange_address, order_id):
        return self.db.query(Order). \
            filter(Order.exchange_address == exchange_address). \
            filter(Order.order_id == order_id). \
            first()


class Processor:
    def __init__(self, web3, sink, db):
        self.web3 = web3
        self.sink = sink
        self.latest_block = web3.eth.blockNumber
        self.db = db

    def get_exchange_list(self):
        tokens = self.db.query(Token). \
            filter(Token.token_address != None). \
            all()
        self.exchange_list = []
        exchange_address_list = []
        for token in tokens:
            token_contract = Contract.get_contract('IbetStandardTokenInterface', token.token_address)
            exchange_address = token_contract.functions.tradableExchange().call()
            if exchange_address not in exchange_address_list:
                exchange_address_list.append(exchange_address)
                if token.template_id == 1:  # 債券トークン
                    self.exchange_list.append(
                        Contract.get_contract('IbetStraightBondExchange', exchange_address)
                    )
                elif token.template_id == 2:  # クーポントークン
                    self.exchange_list.append(
                        Contract.get_contract('IbetCouponExchange', exchange_address)
                    )
                elif token.template_id == 3:  # 会員権トークン
                    self.exchange_list.append(
                        Contract.get_contract('IbetMembershipExchange', exchange_address)
                    )
                else:
                    continue

    def initial_sync(self):
        self.get_exchange_list()
        self.__sync_all(0, self.latest_block)

    def sync_new_logs(self):
        self.get_exchange_list()
        blockTo = web3.eth.blockNumber
        if blockTo == self.latest_block:
            return
        self.__sync_all(self.latest_block + 1, blockTo)
        self.latest_block = blockTo

    def __sync_all(self, block_from, block_to):
        logging.debug("syncing from={}, to={}".format(block_from, block_to))
        self.__sync_new_order(block_from, block_to)
        self.__sync_cancel_order(block_from, block_to)
        self.__sync_agree(block_from, block_to)
        self.sink.flush()

    # Order Event
    def __sync_new_order(self, block_from, block_to):
        for exchange_contract in self.exchange_list:
            try:
                event_filter = exchange_contract.eventFilter(
                    'NewOrder', {
                        'fromBlock': block_from,
                        'toBlock': block_to,
                    }
                )
                for event in event_filter.get_all_entries():
                    args = event['args']
                    if args['price'] > sys.maxsize or args['amount'] > sys.maxsize:
                        pass
                    else:
                        self.sink.on_new_order(
                            token_address=args['tokenAddress'],
                            exchange_address=exchange_contract.address,
                            order_id=args['orderId'],
                            account_address=args['accountAddress'],
                            is_buy=args['isBuy'],
                            price=args['price'],
                            amount=args['amount'],
                            agent_address=args['agentAddress'],
                        )
                self.web3.eth.uninstallFilter(event_filter.filter_id)

            except Exception as e:
                logging.error(e)
                pass

    # CancelOrder Event
    def __sync_cancel_order(self, block_from, block_to):
        for exchange_contract in self.exchange_list:
            try:
                event_filter = exchange_contract.eventFilter(
                    'CancelOrder', {
                        'fromBlock': block_from,
                        'toBlock': block_to,
                    }
                )
                for event in event_filter.get_all_entries():
                    self.sink.on_cancel_order(
                        exchange_address=exchange_contract.address,
                        order_id=event['args']['orderId']
                    )
                self.web3.eth.uninstallFilter(event_filter.filter_id)

            except Exception as e:
                logging.error(e)
                pass

    # Agree Event
    def __sync_agree(self, block_from, block_to):
        for exchange_contract in self.exchange_list:
            try:
                event_filter = exchange_contract.eventFilter(
                    'Agree', {
                        'fromBlock': block_from,
                        'toBlock': block_to,
                    }
                )
                for event in event_filter.get_all_entries():
                    args = event['args']
                    if args['amount'] > sys.maxsize:
                        pass
                    else:
                        order_id = args['orderId']
                        order = exchange_contract.functions.getOrder(order_id).call()
                        order_amount = order[2]
                        self.sink.on_agree(
                            exchange_address=exchange_contract.address,
                            order_id=event['args']['orderId'],
                            order_amount=order_amount
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
    time.sleep(1)
