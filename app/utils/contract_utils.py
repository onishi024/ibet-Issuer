# -*- coding: utf-8 -*-
import json

import boto3
from cryptography.fernet import Fernet
from eth_keyfile import decode_keyfile_json
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

from config import Config
from logging import getLogger

logger = getLogger('api')

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


class ContractUtils:

    @staticmethod
    def get_contract_info(contract_name):
        """コントラクト情報取得

        :param contract_name: コントラクト名
        :return: ABI, bytecode, deployedBytecode
        """
        contract_file = f"contracts/{contract_name}.json"
        contract_json = json.load(open(contract_file, "r"))
        return contract_json["abi"], contract_json["bytecode"], contract_json["deployedBytecode"]

    @staticmethod
    def get_contract(contract_name, address):
        """コントラクト接続

        :param contract_name: コントラクト名
        :param address: コントラクトアドレス
        :return: Contract
        """
        contract_file = f"contracts/{contract_name}.json"
        contract_json = json.load(open(contract_file, "r"))
        contract = web3.eth.contract(
            address=to_checksum_address(address),
            abi=contract_json['abi'],
        )
        return contract

    @staticmethod
    def deploy_contract(contract_name, args, deployer, db_session=None):
        """コントラクトデプロイ

        :param contract_name: コントラクト名
        :param args: コンストラクタに与える引数
        :param deployer: デプロイ実行者
        :param db_session: DBセッション。Flaskアプリ以外（Processor）の場合、必須。
        :return: contract address, ABI, transaction hash
        """
        contract_file = f"contracts/{contract_name}.json"
        contract_json = json.load(open(contract_file, "r"))

        contract = web3.eth.contract(
            abi=contract_json["abi"],
            bytecode=contract_json["bytecode"],
            bytecode_runtime=contract_json["deployedBytecode"],
        )

        tx = contract.constructor(*args).buildTransaction(transaction={'from': deployer, 'gas': Config.TX_GAS_LIMIT})
        tx_hash, txn_receipt = ContractUtils.send_transaction(
            transaction=tx,
            eth_account=deployer,
            db_session=db_session
        )

        contract_address = None
        if txn_receipt is not None:
            # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
            if 'contractAddress' in txn_receipt.keys():
                contract_address = txn_receipt['contractAddress']

        return contract_address, contract_json['abi'], tx_hash

    @staticmethod
    def send_transaction(*, transaction, eth_account, db_session=None):
        """トランザクション送信

        :param transaction: transaction
        :param eth_account: トランザクションを送信する発行体アドレス
        :param db_session: DBセッション。Flaskアプリ以外（Processor）の場合、必須。
        :return: transaction hash, transaction receipt
        """
        from app.models import Issuer

        tx_hash = None

        query = Issuer.query if db_session is None else db_session.query(Issuer)
        issuer = query.filter(Issuer.eth_account == eth_account).first()

        # EOA keyfileのパスワードを取得
        fernet = Fernet(Config.SECURE_PARAMETER_ENCRYPTION_KEY)
        eth_account_password = fernet.decrypt(issuer.encrypted_account_password.encode()).decode()

        if issuer.private_keystore == "GETH":  # keystoreとしてgethを利用する場合
            web3.personal.unlockAccount(issuer.eth_account, eth_account_password, 60)
            tx_hash = web3.eth.sendTransaction(transaction)
        elif issuer.private_keystore == "AWS_SECRETS_MANAGER":  # keystoreとしてAWS Secrets Managerを利用する場合
            nonce = web3.eth.getTransactionCount(issuer.eth_account)
            transaction["nonce"] = nonce
            client = boto3.client(
                service_name="secretsmanager",
                region_name=Config.AWS_REGION_NAME
            )
            keyfile = client.get_secret_value(SecretId=Config.AWS_SECRET_ID)
            keyfile_json = json.loads(keyfile["SecretString"])
            private_key = decode_keyfile_json(keyfile_json, eth_account_password)
            signed = web3.eth.account.signTransaction(transaction, private_key)
            tx_hash = web3.eth.sendRawTransaction(signed.rawTransaction)

        txn_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
        logger.debug("Send Transaction: tx_hash={}, txn_receipt={}".format(tx_hash.hex(), txn_receipt))
        return tx_hash.hex(), txn_receipt
