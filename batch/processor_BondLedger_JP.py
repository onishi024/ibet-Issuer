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
import base64
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
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
from sqlalchemy import (
    create_engine,
    func
)
from sqlalchemy.orm import (
    sessionmaker,
    scoped_session
)
from web3 import Web3
from web3.middleware import geth_poa_middleware

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.utils import ContractUtils
from app.models import (
    Token,
    UTXO,
    BondLedger,
    BondLedgerBlockNumber,
    Issuer,
    CorporateBondLedgerTemplate,
    PersonalInfo as PersonalInfoModel
)
from config import Config

dictConfig(Config.LOG_CONFIG)
log_fmt = '[%(asctime)s] [PROCESSOR-BondLedger] [%(process)d] [%(levelname)s] %(message)s'
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

    def on_utxo(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_utxo(*args, **kwargs)

    def on_bond_ledger(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_bond_ledger(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_utxo(self, spent: bool, transaction_hash: str,
                account_address: str, token_address: str, amount: int,
                block_timestamp: datetime, transaction_date_jst: str):
        if spent is False:
            logging.debug(f"Append UTXO: account_address={account_address}, token_address={token_address}, amount={amount}")
            utxo = self.db.query(UTXO). \
                filter(UTXO.transaction_hash == transaction_hash). \
                first()
            if utxo is None:
                utxo = UTXO()
                utxo.transaction_hash = transaction_hash
                utxo.account_address = account_address
                utxo.token_address = token_address
                utxo.amount = amount
                utxo.block_timestamp = block_timestamp
                utxo.transaction_date_jst = transaction_date_jst
                self.db.add(utxo)
        else:
            logging.debug(f"Spend UTXO: account_address={account_address}, token_address={token_address}, amount={amount}")
            utxo_list = self.db.query(UTXO). \
                filter(UTXO.account_address == account_address). \
                filter(UTXO.token_address == token_address). \
                filter(UTXO.amount > 0). \
                order_by(UTXO.block_timestamp). \
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
                    spend_amount = 0
                    self.db.merge(utxo)

    def on_bond_ledger(self, token):
        #########################################
        # 原簿作成日
        #########################################
        created_date = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(JST).strftime("%Y/%m/%d")

        #########################################
        # 社債の情報
        #########################################
        ledger_template = self.db.query(CorporateBondLedgerTemplate). \
            filter(CorporateBondLedgerTemplate.token_address == token.address). \
            first()

        if ledger_template is not None:
            bond_description = {
                "社債名称": ledger_template.bond_name,
                "社債の説明": ledger_template.bond_description,
                "社債の総額": ledger_template.total_amount,
                "各社債の金額": ledger_template.face_value,
                "払込情報": {
                    "払込金額": ledger_template.payment_amount,
                    "払込日": ledger_template.payment_date,
                    "払込状況": ledger_template.payment_status
                },
                "社債の種類": ledger_template.bond_type
            }
        else:
            bond_description = {
                "社債名称": "",
                "社債の説明": "",
                "社債の総額": None,
                "各社債の金額": None,
                "払込情報": {
                    "払込金額": None,
                    "払込日": "",
                    "払込状況": None
                },
                "社債の種類": ""
            }

        #########################################
        # 原簿管理人
        #########################################
        if ledger_template is not None:
            ledger_admin = {
                "氏名または名称": ledger_template.ledger_admin_name,
                "住所": ledger_template.ledger_admin_address,
                "事務取扱場所": ledger_template.ledger_admin_location
            }
        else:
            ledger_admin = {
                "氏名または名称": "",
                "住所": "",
                "事務取扱場所": ""
            }

        #########################################
        # 債権者情報
        #########################################
        issuer_address = token.functions.owner().call()
        face_value = token.functions.faceValue().call()

        utxo_list = self.db.query(UTXO.account_address, UTXO.token_address, func.sum(UTXO.amount),
                                  UTXO.transaction_date_jst). \
            filter(UTXO.token_address == token.address). \
            filter(UTXO.amount > 0). \
            group_by(UTXO.account_address, UTXO.token_address, UTXO.transaction_date_jst). \
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
                "社債金額": face_value * amount,
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
                },
                "備考": "-"
            }

            # 個人情報取得
            personal_info_json = self.__get_personalinfo_from_db(
                account_address=account_address,
                issuer_address=issuer_address
            )
            if personal_info_json is None:  # DBに情報が登録されていない場合はコントラクトから情報を取得する
                personal_info_contract_address = token.functions.personalInfoAddress().call()
                personal_info_json = self.__get_personalinfo_from_contract(
                    account_address=account_address,
                    issuer_address=issuer_address,
                    personal_info_contract_address=personal_info_contract_address
                )

            if personal_info_json is not None:
                name = personal_info_json.get("name", "")  # 氏名
                address = personal_info_json.get("address", "")  # 住所
            else:
                name = ""
                address = ""

            # 保有者情報設定
            details["氏名または名称"] = name
            details["住所"] = address
            creditors.append(details)

        # 原簿保管
        ledger = {
            "社債原簿作成日": created_date,
            "社債情報": bond_description,
            "社債原簿管理人": ledger_admin,
            "社債権者": creditors
        }
        bond_ledger = BondLedger(
            token_address=token.address,
            ledger=json.dumps(ledger, ensure_ascii=False).encode()
        )
        self.db.add(bond_ledger)

    def __get_personalinfo_from_db(self, account_address: str, issuer_address: str):
        """個人情報取得（DB）

        :param account_address: アカウントアドレス
        :param issuer_address: 発行体アドレス
        :return: 個人情報JSON
        """
        # 個人情報取得
        personal_info_record = self.db.query(PersonalInfoModel). \
            filter(PersonalInfoModel.account_address == to_checksum_address(account_address)). \
            filter(PersonalInfoModel.issuer_address == to_checksum_address(issuer_address)). \
            first()
        if personal_info_record is not None:
            personal_info_json = personal_info_record.personal_info
        else:
            personal_info_json = None

        return personal_info_json

    def __get_personalinfo_from_contract(self, account_address: str, issuer_address: str,
                                         personal_info_contract_address: str):
        """個人情報取得（コントラクト）

        :param account_address: アカウントアドレス
        :param issuer_address: 発行体アドレス
        :param personal_info_contract_address: 個人情報コントラクトアドレス
        :return: 個人情報JSON
        """
        personal_info_json = None

        try:
            issuer = self.db.query(Issuer).filter(Issuer.eth_account == issuer_address).first()

            personal_info_contract = ContractUtils.get_contract('PersonalInfo', personal_info_contract_address)
            cipher = None
            try:
                key = RSA.importKey(issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
                cipher = PKCS1_OAEP.new(key)
            except Exception as err:
                logging.error(f"Cannot open the private key: {err}")

            # 暗号化個人情報取得
            personal_info = personal_info_contract.functions. \
                personal_info(account_address, issuer_address). \
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
        except Exception as err:
            logging.error(f"Failed to decrypt: {err} : account_address = {account_address}")

        return personal_info_json

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
        if ledger_block_number >= latest_block:
            logging.debug("skip process")
            pass
        else:
            logging.info("syncing from={}, to={}".format(ledger_block_number + 1, latest_block))
            for token in self.token_list:
                event_triggered = self.__create_utxo(token, ledger_block_number + 1, latest_block)
                if event_triggered:  # UTXOの更新イベントが発生している場合
                    self.__create_ledger(token)
            self.__set_ledger_blocknumber(latest_block)
            self.sink.flush()

    def __refresh_token_list(self):
        """発行済トークンの直近化

        :return: None
        """
        self.token_list = []
        issued_tokens = self.db.query(Token). \
            filter(Token.template_id == Config.TEMPLATE_ID_SB). \
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

    def __create_utxo(self, token, from_block: int, to_block: int) -> bool:
        """UTXO作成（Transferイベント発生時）

        :param token: token contract
        :param from_block: from block number
        :param to_block:  to block number
        :return: event_triggered イベント発生
        """
        event_triggered = False
        events = token.events.Transfer.getLogs(
            fromBlock=from_block,
            toBlock=to_block
        )
        for event in events:
            event_triggered = True

            transaction_hash = event["transactionHash"].hex()
            args = event["args"]
            from_account = args.get("from", Config.ZERO_ADDRESS)
            to_account = args.get("to", Config.ZERO_ADDRESS)
            amount = args.get("value")
            block_timestamp = datetime.fromtimestamp(
                web3.eth.getBlock(event['blockNumber'])['timestamp']
            )
            block_timestamp_jst = block_timestamp.replace(tzinfo=timezone.utc). \
                astimezone(JST)
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
        return event_triggered

    def __create_ledger(self, token):
        """原簿作成

        :param token: token contract
        """
        self.sink.on_bond_ledger(token=token)


sinks = Sinks()
sinks.register(DBSink(db_session))
processor = Processor(db=db_session, sink=sinks)

while True:
    try:
        processor.process()
        logging.debug("processed")
    except Exception as ex:
        logging.exception(ex)

    # 1分間隔で実行
    time.sleep(60)
