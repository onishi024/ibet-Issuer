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
from app.models import Token, Agreement, AgreementStatus
from app.utils import ContractUtils
from config import Config
from web3.middleware import geth_poa_middleware

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
dictConfig(Config.LOG_CONFIG)
log_fmt = '[%(asctime)s] [INDEXER-Agreement] [%(process)d] [%(levelname)s] %(message)s'
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

    def on_agree(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_agree(*args, **kwargs)

    def on_settlement_ok(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_settlement_ok(*args, **kwargs)

    def on_settlement_ng(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_settlement_ng(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class ConsoleSink:
    @staticmethod
    def on_agree(token_address, exchange_address, order_id, agreement_id,
                 buyer_address, seller_address, price, amount, agent_address):
        logging.info(
            "Agree: exchange_address={}, order_id={}, agreement_id={}".format(
                exchange_address, order_id, agreement_id
            )
        )

    @staticmethod
    def on_settlement_ok(exchange_address, order_id, agreement_id):
        logging.info(
            "SettlementOK: exchange_address={}, orderId={}, agreementId={}".format(
                exchange_address, order_id, agreement_id
            )
        )

    @staticmethod
    def on_settlement_ng(exchange_address, order_id, agreement_id):
        logging.info(
            "SettlementNG: exchange_address={}, orderId={}, agreementId={}".format(
                exchange_address, order_id, agreement_id
            )
        )

    def flush(self):
        return


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_agree(self, token_address, exchange_address, order_id, agreement_id,
                 buyer_address, seller_address, price, amount, agent_address):
        agreement = self.__get_agreement(exchange_address, order_id, agreement_id)
        if agreement is None:
            agreement = Agreement()
            agreement.token_address = token_address
            agreement.exchange_address = exchange_address
            agreement.order_id = order_id
            agreement.agreement_id = agreement_id
            agreement.unique_order_id = exchange_address + '_' + str(order_id)
            agreement.buyer_address = buyer_address
            agreement.seller_address = seller_address
            agreement.price = price
            agreement.amount = amount
            agreement.agent_address = agent_address
            agreement.status = AgreementStatus.PENDING.value
            self.db.merge(agreement)

    def on_settlement_ok(self, exchange_address, order_id, agreement_id):
        agreement = self.__get_agreement(exchange_address, order_id, agreement_id)
        if agreement is not None:
            agreement.status = AgreementStatus.DONE.value

    def on_settlement_ng(self, exchange_address, order_id, agreement_id):
        agreement = self.__get_agreement(exchange_address, order_id, agreement_id)
        if agreement is not None:
            agreement.status = AgreementStatus.CANCELED.value

    def flush(self):
        self.db.commit()

    def __get_agreement(self, exchange_address, order_id, agreement_id):
        return self.db.query(Agreement). \
            filter(Agreement.exchange_address == exchange_address). \
            filter(Agreement.order_id == order_id). \
            filter(Agreement.agreement_id == agreement_id). \
            first()


class Processor:
    def __init__(self, sink, db):
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
            token_contract = ContractUtils.get_contract('IbetStandardTokenInterface', token.token_address)
            try:
                exchange_address = token_contract.functions.tradableExchange().call()
            except Exception as e:
                logging.warning(e)
                continue
            if exchange_address not in exchange_address_list:
                exchange_address_list.append(exchange_address)
                if token.template_id == 1:  # 債券トークン
                    self.exchange_list.append(
                        ContractUtils.get_contract('IbetStraightBondExchange', exchange_address)
                    )
                elif token.template_id == 2:  # クーポントークン
                    self.exchange_list.append(
                        ContractUtils.get_contract('IbetCouponExchange', exchange_address)
                    )
                elif token.template_id == 3:  # 会員権トークン
                    self.exchange_list.append(
                        ContractUtils.get_contract('IbetMembershipExchange', exchange_address)
                    )
                else:
                    continue

    def initial_sync(self):
        self.get_exchange_list()
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
        self.get_exchange_list()
        blockTo = web3.eth.blockNumber
        if blockTo == self.latest_block:
            return
        self.__sync_all(self.latest_block + 1, blockTo)
        self.latest_block = blockTo

    def __sync_all(self, block_from, block_to):
        logging.debug("syncing from={}, to={}".format(block_from, block_to))
        self.__sync_agree(block_from, block_to)
        self.__sync_settlement_ok(block_from, block_to)
        self.__sync_settlement_ng(block_from, block_to)
        self.sink.flush()

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
                        self.sink.on_agree(
                            token_address=args['tokenAddress'],
                            exchange_address=exchange_contract.address,
                            order_id=args['orderId'],
                            agreement_id=args['agreementId'],
                            buyer_address=args['buyAddress'],
                            seller_address=args['sellAddress'],
                            price=args['price'],
                            amount=args['amount'],
                            agent_address=args['agentAddress']
                        )
                web3.eth.uninstallFilter(event_filter.filter_id)
            except Exception as e:
                logging.error(e)

    # SettlementOK Event
    def __sync_settlement_ok(self, block_from, block_to):
        for exchange_contract in self.exchange_list:
            try:
                event_filter = exchange_contract.eventFilter(
                    'SettlementOK', {
                        'fromBlock': block_from,
                        'toBlock': block_to,
                    }
                )
                for event in event_filter.get_all_entries():
                    args = event['args']
                    self.sink.on_settlement_ok(
                        exchange_address=exchange_contract.address,
                        order_id=args['orderId'],
                        agreement_id=args['agreementId']
                    )
                web3.eth.uninstallFilter(event_filter.filter_id)
            except Exception as e:
                logging.error(e)

    # SettlementNG Event
    def __sync_settlement_ng(self, block_from, block_to):
        for exchange_contract in self.exchange_list:
            try:
                event_filter = exchange_contract.eventFilter(
                    'SettlementNG', {
                        'fromBlock': block_from,
                        'toBlock': block_to,
                    }
                )
                for event in event_filter.get_all_entries():
                    args = event['args']
                    self.sink.on_settlement_ng(
                        exchange_address=exchange_contract.address,
                        order_id=args['orderId'],
                        agreement_id=args['agreementId']
                    )
                web3.eth.uninstallFilter(event_filter.filter_id)
            except Exception as e:
                logging.error(e)


_sink = Sinks()
_sink.register(ConsoleSink())
_sink.register(DBSink(db_session))
processor = Processor(sink=_sink, db=db_session)

processor.initial_sync()
while True:
    processor.sync_new_logs()
    time.sleep(1)
