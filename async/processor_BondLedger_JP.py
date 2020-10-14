# -*- coding: utf-8 -*-
import base64
import json
import os
import sys
import time
import logging
from logging.config import dictConfig

from datetime import datetime, timezone, timedelta
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA

from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker, scoped_session

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.utils import ContractUtils
from app.models import Token, UTXO, BondLedger, BondLedgerBlockNumber, Issuer
from config import Config

from web3 import Web3
from web3.middleware import geth_poa_middleware

# NOTE:ログフォーマットはメッセージ監視が出来るように設定する必要がある。
dictConfig(Config.LOG_CONFIG)
log_fmt = 'PROCESSOR-BondLedger [%(asctime)s] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(format=log_fmt)

# 設定の取得
WEB3_HTTP_PROVIDER = Config.WEB3_HTTP_PROVIDER
URI = Config.SQLALCHEMY_DATABASE_URI
JST = timezone(timedelta(hours=+9), "JST")

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

    def on_utxo(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_utxo(*args, **kwargs)

    def on_bond_ledger(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_bond_ledger(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class ConsoleSink:
    @staticmethod
    def on_utxo(spent: bool, transaction_hash: str,
                account_address: str, token_address: str, amount: int,
                block_timestamp: datetime, transaction_date_jst: str):
        if spent is False:
            logging.info(
                f"Append UTXO: account_address={account_address}, token_address={token_address}, amount={amount}"
            )
        else:
            logging.info(
                f"Spend UTXO: account_address={account_address}, token_address={token_address}, amount={amount}"
            )

    @staticmethod
    def on_bond_ledger(token):
        logging.info(f"Create New Ledger: token_address={token.address}")

    def flush(self):
        return


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_utxo(self, spent: bool, transaction_hash: str,
                account_address: str, token_address: str, amount: int,
                block_timestamp: datetime, transaction_date_jst: str):
        if spent is False:
            utxo = UTXO()
            utxo.transaction_hash = transaction_hash
            utxo.account_address = account_address
            utxo.token_address = token_address
            utxo.amount = amount
            utxo.block_timestamp = block_timestamp
            utxo.transaction_date_jst = transaction_date_jst
            self.db.add(utxo)
        else:
            utxo_list = self.db.query(UTXO).\
                filter(UTXO.account_address == account_address).\
                filter(UTXO.token_address == token_address).\
                filter(UTXO.amount > 0).\
                order_by(UTXO.block_timestamp).\
                all()
            spend_amount = amount
            for utxo in utxo_list:
                utxo_amount = utxo.amount
                if spend_amount <= 0:
                    pass
                elif utxo.amount <= spend_amount:
                    utxo.amount = 0
                    spend_amount = spend_amount - utxo_amount
                    self.db.merge(utxo)
                else:
                    utxo.amount = utxo_amount - spend_amount
                    self.db.merge(utxo)

    def on_bond_ledger(self, token):
        # 原簿作成日
        created_date = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(JST).strftime("%Y/%m/%d")

        # 債券情報
        bond_description = {
            "名称": token.functions.name().call(),
            "説明": token.functions.purpose().call(),
            "総額": token.functions.faceValue().call() * token.functions.totalSupply().call(),
            "各債券の金額": token.functions.faceValue().call(),
            "その他補足事項": token.functions.memo().call()
        }

        # 原簿管理人
        # TODO:DBから取得する
        ledger_admin = {
            "名称": "aaa",
            "住所": "bbb",
            "事務取扱場所": "ccc"
        }

        # 債権者情報
        issuer_address = token.functions.owner().call()
        issuer = self.db.query(Issuer).filter(Issuer.eth_account == issuer_address).first()
        personal_info_contract_address = token.functions.personalInfoAddress().call()
        personal_info_contract = ContractUtils.get_contract('PersonalInfo', personal_info_contract_address)
        cipher = None
        try:
            key = RSA.importKey(issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
            cipher = PKCS1_OAEP.new(key)
        except Exception as err:
            logging.error(f"Cannot open the private key: {err}")

        utxo_list = self.db.query(UTXO.account_address, UTXO.token_address, func.sum(UTXO.amount), UTXO.transaction_date_jst).\
            filter(UTXO.token_address == token.address).\
            filter(UTXO.amount > 0).\
            group_by(UTXO.account_address, UTXO.token_address, UTXO.transaction_date_jst).\
            all()

        creditors = []
        for utxo in utxo_list:
            account_address = utxo[0]
            amount = utxo[2]
            transaction_date_jst = utxo[3]

            # 初期値設定
            details = {
                "アカウントアドレス": account_address,
                "氏名または名称": "",
                "住所": "",
                "金額": amount,
                "取得日": transaction_date_jst
            }

            try:
                # 暗号化個人情報取得
                personal_info = personal_info_contract.functions.\
                    personal_info(account_address, issuer_address).\
                    call()
                encrypted_personal_info = personal_info[2]

                if encrypted_personal_info != '' and cipher is not None:  # 情報が空の場合、デフォルト値を設定
                    # 個人情報復号化
                    ciphertext = base64.decodebytes(encrypted_personal_info.encode('utf-8'))
                    # NOTE:
                    # JavaScriptでRSA暗号化する際に、先頭が0x00の場合は00を削った状態でデータが連携される。
                    # そのままdecryptすると、ValueError（Ciphertext with incorrect length）になるため、
                    # 先頭に再度00を加えて、decryptを行う。
                    if len(ciphertext) == 1279:
                        hex_fixed = "00" + ciphertext.hex()
                        ciphertext = base64.b16decode(hex_fixed.upper())
                    message = cipher.decrypt(ciphertext)
                    personal_info_json = json.loads(message)

                    # 氏名
                    name = personal_info_json.get("name", "")

                    # 住所
                    address_details = personal_info_json.get("address", {})
                    address = f'{address_details.get("prefecture", "")}' \
                              f'{address_details.get("city", "")} ' \
                              f'{address_details.get("address1", "")} ' \
                              f'{address_details.get("address2", "")}'

                    # 保有者情報
                    details = {
                        "アカウントアドレス": account_address,
                        "氏名または名称": name,
                        "住所": address,
                        "金額": amount,
                        "取得日": transaction_date_jst,
                        "金銭以外の財産給付情報": {
                            "財産の価格": "-",
                            "給付日": "-"
                        },
                        "債権相殺情報": {
                            "相殺する債権額": "-",
                            "相殺日": "-"
                        },
                        "質権情報": {
                            "質権者の氏名または名称": "-",
                            "質権者の住所": "-",
                            "質権の目的である債券": "-"
                        }
                    }
            except Exception as err:  # 復号化処理でエラーが発生した場合、デフォルト値を設定
                pass
                # logging.error(f"Failed to decrypt: {err}")

            creditors.append(details)

        # 原簿保管
        ledger = {
            "原簿作成日": created_date,
            "債券情報": bond_description,
            "原簿管理人": ledger_admin,
            "債権者": creditors
        }
        bond_ledger = BondLedger(
            token_address=token.address,
            ledger=json.dumps(ledger, ensure_ascii=False).encode()
        )
        self.db.add(bond_ledger)

    def flush(self):
        self.db.commit()


class Processor:
    def __init__(self, db, sink):
        self.sink = sink
        self.db = db
        self.token_list = []

    def process(self):
        self.__refresh_token_list()
        ledger_block_number = self.__get_ledger_blocknumber()
        latest_block = web3.eth.blockNumber
        if ledger_block_number == latest_block:
            logging.debug("skip process")
            pass
        else:
            for token in self.token_list:
                self.__process_transfer(token, ledger_block_number, latest_block)
            self.__set_ledger_blocknumber(latest_block)
            self.sink.flush()

    def __refresh_token_list(self):
        """発行済トークンの直近化

        :return: None
        """
        self.token_list = []
        issued_tokens = self.db.query(Token).\
            filter(Token.template_id == Config.TEMPLATE_ID_SB).\
            all()
        for issued_token in issued_tokens:
            if issued_token.token_address is not None:
                abi = json.loads(issued_token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))
                token_contract = web3.eth.contract(
                    address=issued_token.token_address,
                    abi=abi
                )
                self.token_list.append(token_contract)

    def __get_ledger_blocknumber(self):
        block_number = self.db.query(BondLedgerBlockNumber).first()
        if block_number is None:
            return 0
        else:
            return block_number.latest_block_number

    def __set_ledger_blocknumber(self, block_number: int):
        """latest block number の設定

        :param block_number: 設定するblockNumber
        :return: None
        """
        ledger_block = self.db.query(BondLedgerBlockNumber).first()
        if ledger_block is None:
            ledger_block = BondLedgerBlockNumber()
            ledger_block.latest_block_number = block_number
        else:
            ledger_block.latest_block_number = block_number
        self.db.merge(ledger_block)

    def __process_transfer(self, token, from_block: int, to_block: int):
        """台帳作成（Transferイベント発生時）

        :param token: token contract
        :param from_block: from block number
        :param to_block:  to block number
        :return: None
        """
        event_filter = token.eventFilter(
            "Transfer", {
                "fromBlock": from_block,
                "toBlock": to_block,
            }
        )
        for event in event_filter.get_all_entries():
            transaction_hash = event["transactionHash"].hex()
            args = event["args"]
            from_account = args.get("from", Config.ZERO_ADDRESS)
            to_account = args.get("to", Config.ZERO_ADDRESS)
            amount = args.get("value")
            block_timestamp = datetime.fromtimestamp(
                web3.eth.getBlock(event['blockNumber'])['timestamp'],
                JST
            )
            block_timestamp_jst = block_timestamp.replace(tzinfo=timezone.utc).astimezone(JST)
            transaction_date_jst = block_timestamp_jst.strftime("%Y/%m/%d")

            if amount is not None and amount <= sys.maxsize:
                # UTXOの更新（from account）
                self.sink.on_utxo(
                    spent=True,
                    transaction_hash=transaction_hash,
                    token_address=token.address,
                    account_address=from_account,
                    amount=amount,
                    block_timestamp=block_timestamp,
                    transaction_date_jst=transaction_date_jst
                )

                # UTXOの更新（to account）
                self.sink.on_utxo(
                    spent=False,
                    transaction_hash=transaction_hash,
                    token_address=token.address,
                    account_address=to_account,
                    amount=amount,
                    block_timestamp=block_timestamp,
                    transaction_date_jst=transaction_date_jst
                )

                # Ledgeデータの作成
                self.sink.on_bond_ledger(
                    token=token
                )

        web3.eth.uninstallFilter(event_filter.filter_id)


sinks = Sinks()
sinks.register(ConsoleSink())
sinks.register(DBSink(db_session))
processor = Processor(db=db_session, sink=sinks)

while True:
    try:
        processor.process()
        logging.debug("processed")
    except Exception as ex:
        logging.exception(ex)

    # 10分間隔で実行
    time.sleep(600)
