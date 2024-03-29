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
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    sessionmaker,
    scoped_session
)
from web3 import Web3
from web3.middleware import geth_poa_middleware
from web3.exceptions import BadFunctionCallOutput

path = os.path.join(os.path.dirname(__file__), '../')
sys.path.append(path)

from app.models import (
    Token,
    Issuer,
    PersonalInfoBlockNumber
)
from app.models import PersonalInfo as PersonalInfoModel
from config import Config

dictConfig(Config.LOG_CONFIG)
log_fmt = '[%(asctime)s] [INDEXER-PersonalInfo] [%(process)d] [%(levelname)s] %(message)s'
logging.basicConfig(format=log_fmt)

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)

JST = timezone(timedelta(hours=+9), "JST")


class PersonalInfoContract:
    """PersonalInfoコントラクト"""

    def __init__(self, issuer_address: str, custom_personal_info_address=None):
        issuer = db_session.query(Issuer). \
            filter(Issuer.eth_account == to_checksum_address(issuer_address)). \
            first()
        self.issuer = issuer

        if custom_personal_info_address is None:
            contract_address = issuer.personal_info_contract_address
        else:
            contract_address = to_checksum_address(custom_personal_info_address)
        contract_file = f"contracts/PersonalInfo.json"
        contract_json = json.load(open(contract_file, "r"))
        self.personal_info_contract = web3.eth.contract(
            address=to_checksum_address(contract_address),
            abi=contract_json['abi'],
        )

    def get_info(self, account_address: str, default_value=None):
        """個人情報取得

        :param account_address: トークン保有者のアドレス
        :param default_value: 値が未設定の項目に設定する初期値。(未指定時: None)
        :return: personal info
        """

        # 発行体のRSA秘密鍵の取得
        cipher = None
        try:
            key = RSA.importKey(self.issuer.encrypted_rsa_private_key, Config.RSA_PASSWORD)
            cipher = PKCS1_OAEP.new(key)
        except Exception as err:
            logging.error(f"Cannot open the private key: {err}")

        # デフォルト値を設定
        personal_info = {
            "key_manager": default_value,
            "name": default_value,
            "postal_code": default_value,
            "address": default_value,
            "email": default_value,
            "birth": default_value
        }

        # 個人情報（暗号化）取得
        personal_info_state = self.personal_info_contract.functions. \
            personal_info(account_address, self.issuer.eth_account). \
            call()
        encrypted_info = personal_info_state[2]

        if encrypted_info == '' or cipher is None:
            return personal_info  # デフォルトの情報を返却
        else:
            try:
                ciphertext = base64.decodebytes(encrypted_info.encode('utf-8'))
                # NOTE:
                # JavaScriptでRSA暗号化する際に、先頭が0x00の場合は00を削った状態でデータが連携される。
                # そのままdecryptすると、ValueError（Ciphertext with incorrect length）になるため、
                # 先頭に再度00を加えて、decryptを行う。
                if len(ciphertext) == 1279:
                    hex_fixed = "00" + ciphertext.hex()
                    ciphertext = base64.b16decode(hex_fixed.upper())
                decrypted_info = json.loads(cipher.decrypt(ciphertext))

                personal_info["key_manager"] = decrypted_info.get("key_manager", default_value)
                personal_info["name"] = decrypted_info.get("name", default_value)
                personal_info["address"] = decrypted_info.get("address", default_value)
                personal_info["postal_code"] = decrypted_info.get("postal_code", default_value)
                personal_info["email"] = decrypted_info.get("email", default_value)
                personal_info["birth"] = decrypted_info.get("birth", default_value)
                return personal_info
            except Exception as err:
                logging.error(f"Failed to decrypt: {err}")
                return personal_info  # デフォルトの情報を返却

    def get_register_event(self, block_from, block_to):
        """Registerイベントの取得

        :param block_from: block from
        :param block_to: block to
        :return: event entries
        """
        events = self.personal_info_contract.events.Register.getLogs(
            fromBlock=block_from,
            toBlock=block_to
        )
        return events

    def get_modify_event(self, block_from, block_to):
        """Modifyイベントの取得

        :param block_from: block from
        :param block_to: block to
        :return: event entries
        """
        events = self.personal_info_contract.events.Modify.getLogs(
            fromBlock=block_from,
            toBlock=block_to
        )
        return events


class Sinks:
    def __init__(self):
        self.sinks = []

    def register(self, sink):
        self.sinks.append(sink)

    def on_personalinfo_register(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_personalinfo_register(*args, **kwargs)

    def on_personalinfo_modify(self, *args, **kwargs):
        for sink in self.sinks:
            sink.on_personalinfo_modify(*args, **kwargs)

    def flush(self, *args, **kwargs):
        for sink in self.sinks:
            sink.flush(*args, **kwargs)


class DBSink:
    def __init__(self, db):
        self.db = db

    def on_personalinfo_register(self, account_address, issuer_address, personal_info, timestamp):
        logging.debug(f"Register: account_address={account_address}, issuer_address={issuer_address}")
        record = self.db.query(PersonalInfoModel). \
            filter(PersonalInfoModel.account_address == to_checksum_address(account_address)). \
            filter(PersonalInfoModel.issuer_address == to_checksum_address(issuer_address)). \
            first()
        if record is not None:
            record.personal_info = personal_info
            record.modified = timestamp
            self.db.merge(record)
        else:
            record = PersonalInfoModel()
            record.account_address = account_address
            record.issuer_address = issuer_address
            record.personal_info = personal_info
            record.created = timestamp
            record.modified = timestamp
            self.db.add(record)

    def on_personalinfo_modify(self, account_address, issuer_address, personal_info, timestamp):
        logging.debug(f"Modify: account_address={account_address}, issuer_address={issuer_address}")
        record = self.db.query(PersonalInfoModel). \
            filter(PersonalInfoModel.account_address == to_checksum_address(account_address)). \
            filter(PersonalInfoModel.issuer_address == to_checksum_address(issuer_address)). \
            first()
        if record is not None:
            record.personal_info = personal_info
            record.modified = timestamp
            self.db.merge(record)

    def flush(self):
        self.db.commit()


class Processor:
    def __init__(self, sink, db):
        self.sink = sink
        self.latest_block = web3.eth.blockNumber
        self.db = db
        self.personalinfo_list = []

    def process(self):
        self.__refresh_personalinfo_list()
        block_number = self.__get_blocknumber()  # DB同期済の直近のblockNumber
        latest_block = web3.eth.blockNumber  # 現在の最新のblockNumber
        logging.info("syncing from={}, to={}".format(block_number, latest_block))
        if block_number >= latest_block:
            logging.debug("Skip Process")
        else:
            self.__sync_all(block_number + 1, latest_block)
            self.__set_blocknumber(latest_block)
            self.sink.flush()

    def __refresh_personalinfo_list(self):
        self.personalinfo_list.clear()
        # 発行済のトークンのリストを取得
        _tokens = self.db.query(Token).all()
        # issuer-address , personalinfo-address の組み合わせのリストを取得
        tmp_list = []
        for _token in _tokens:
            if _token.token_address is not None:
                if _token.template_id == Config.TEMPLATE_ID_SB or _token.template_id == Config.TEMPLATE_ID_SHARE:
                    try:
                        abi = json.loads(
                            _token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false')
                        )
                        token_contract = web3.eth.contract(
                            address=_token.token_address,
                            abi=abi
                        )
                        personalinfo_address = token_contract.functions.personalInfoAddress().call()
                        tmp_list.append({
                            "issuer_address": _token.admin_address,
                            "personalinfo_address": personalinfo_address
                        })
                    except BadFunctionCallOutput:
                        logging.warning(f"Failed to get the PersonalInfo address: token = {_token.token_address}")
                else:
                    tmp_list.append({
                        "issuer_address": _token.admin_address,
                        "personalinfo_address": None
                    })
        # リストの重複を排除する
        unique_list = list(map(json.loads, set(map(json.dumps, tmp_list))))
        # PersonalInfoContract のリストを取得
        for item in unique_list:
            personalinfo_contract = PersonalInfoContract(
                issuer_address=item["issuer_address"],
                custom_personal_info_address=item["personalinfo_address"]
            )
            self.personalinfo_list.append(personalinfo_contract)

    def __get_blocknumber(self):
        """DB同期済の直近blockNumberを取得

        :return: 同期済の直近blockNumber
        """
        block_number = self.db.query(PersonalInfoBlockNumber).first()
        if block_number is None:
            return 0
        else:
            return block_number.latest_block_number

    def __set_blocknumber(self, block_number: int):
        """DB同期済の直近blockNumberの設定

        :param block_number: 設定するblockNumber
        :return: None
        """
        personalinfo_block_number = self.db.query(PersonalInfoBlockNumber).first()
        if personalinfo_block_number is None:
            personalinfo_block_number = PersonalInfoBlockNumber()
            personalinfo_block_number.latest_block_number = block_number
        else:
            personalinfo_block_number.latest_block_number = block_number
        self.db.merge(personalinfo_block_number)

    def __sync_all(self, block_from: int, block_to: int):
        self.__sync_personalinfo_register(block_from, block_to)
        self.__sync_personalinfo_modify(block_from, block_to)

    def __sync_personalinfo_register(self, block_from, block_to):
        for _personalinfo in self.personalinfo_list:
            try:
                register_event_list = _personalinfo.get_register_event(block_from, block_to)
                for event in register_event_list:
                    args = event["args"]
                    account_address = args.get("account_address", Config.ZERO_ADDRESS)
                    link_address = args.get("link_address", Config.ZERO_ADDRESS)
                    if link_address == _personalinfo.issuer.eth_account:
                        block = web3.eth.getBlock(event["blockNumber"])
                        timestamp = datetime.fromtimestamp(block["timestamp"])
                        decrypted_personalinfo = _personalinfo.get_info(account_address=account_address)
                        self.sink.on_personalinfo_register(
                            account_address=account_address,
                            issuer_address=link_address,
                            personal_info=decrypted_personalinfo,
                            timestamp=timestamp
                        )
                        self.sink.flush()
            except Exception as err:
                logging.error(err)

    def __sync_personalinfo_modify(self, block_from, block_to):
        for _personalinfo in self.personalinfo_list:
            try:
                register_event_list = _personalinfo.get_modify_event(block_from, block_to)
                for event in register_event_list:
                    args = event["args"]
                    account_address = args.get("account_address", Config.ZERO_ADDRESS)
                    link_address = args.get("link_address", Config.ZERO_ADDRESS)
                    if link_address == _personalinfo.issuer.eth_account:
                        block = web3.eth.getBlock(event["blockNumber"])
                        timestamp = datetime.fromtimestamp(block["timestamp"])
                        decrypted_personalinfo = _personalinfo.get_info(account_address=account_address)
                        self.sink.on_personalinfo_modify(
                            account_address=account_address,
                            issuer_address=link_address,
                            personal_info=decrypted_personalinfo,
                            timestamp=timestamp
                        )
                        self.sink.flush()
            except Exception as err:
                logging.error(err)


_sink = Sinks()
_sink.register(DBSink(db_session))
processor = Processor(sink=_sink, db=db_session)
logging.info("Service started successfully")

while True:
    try:
        processor.process()
        logging.debug("Processed")
    except Exception as ex:
        logging.exception(ex)

    time.sleep(Config.INTERVAL_INDEXER_PERSONAL_INFO)
