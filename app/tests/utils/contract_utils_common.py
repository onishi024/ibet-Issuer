# -*- coding: utf-8 -*-
from datetime import datetime
from logging import getLogger

from web3 import Web3
from web3.middleware import geth_poa_middleware

from app.models import Token, Transfer, Consume
from config import Config

logger = getLogger('api')
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


def processor_issue_event(db):
    """
    発行済みトークンのアドレスをDBへ登録
    :param db: pytest fixture
    :return: なし
    """
    tokens = Token.query.all()
    for token in tokens:
        if token.token_address is None:  # コントラクトアドレスが登録されていないTokenの一覧を抽出
            tx_hash = token.tx_hash
            tx_hash_hex = '0x' + tx_hash[2:]
            try:
                tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash_hex)
            except Exception as e:
                logger.error(e)
                continue
            if tx_receipt is not None:
                # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
                if 'contractAddress' in tx_receipt.keys():
                    admin_address = tx_receipt['from']
                    contract_address = tx_receipt['contractAddress']

                    # 登録済みトークン情報に発行者のアドレスと、トークンアドレスの登録を行う。
                    token.admin_address = admin_address
                    token.token_address = contract_address
                    db.session.add(token)


def clean_issue_event(db):
    """
    発行済みトークンの削除処理
    :return: なし
    """
    Token.query.delete()
    db.session.execute("ALTER SEQUENCE tokens_id_seq RESTART WITH 1")


def index_transfer_event(db, transaction_hash, token_address, account_address_from, account_address_to, amount,
                         block_timestamp=None):
    """
    任意のTransferイベントをDBに登録
    :param db: pytest fixture
    :param transaction_hash: トランザクションハッシュ
    :param token_address: トークンアドレス
    :param account_address_from: Fromアカウントアドレス
    :param account_address_to: Toアカウントアドレス
    :param amount: 移転数量
    :param block_timestamp: ブロックタイムスタンプ
    :return: なし
    """
    record = Transfer()
    record.transaction_hash = transaction_hash
    record.token_address = token_address
    record.account_address_from = account_address_from
    record.account_address_to = account_address_to
    record.transfer_amount = amount
    record.block_timestamp = block_timestamp
    db.session.add(record)


def index_consume_event(db, transaction_hash, token_address, consumer_address, balance, total_used_amount, used_amount,
                        block_timestamp=None):
    """
    任意のConsumeイベントをDBに登録

    :param db: pytest fixture
    :param transaction_hash: トランザクションハッシュ
    :param token_address: トークンアドレス
    :param consumer_address: トークン消費者アドレス
    :param balance: 保有残高
    :param total_used_amount: 累計消費数量
    :param used_amount: 消費数量
    :param block_timestamp: ブロックタイムスタンプ (UTC) (省略時: 現在時刻)
    :return: なし
    """
    record = Consume()
    record.transaction_hash = transaction_hash
    record.token_address = token_address
    record.consumer_address = consumer_address
    record.balance = balance
    record.total_used_amount = total_used_amount
    record.used_amount = used_amount
    record.block_timestamp = block_timestamp or datetime.utcnow()
    db.session.add(record)

    return record
