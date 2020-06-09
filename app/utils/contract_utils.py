# -*- coding: utf-8 -*-
import json

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
        contract_file = f"contracts/{contract_name}.json"
        contract_json = json.load(open(contract_file, "r"))
        return contract_json["abi"], contract_json["bytecode"], contract_json["deployedBytecode"]

    @staticmethod
    def get_contract(contract_name, address):
        contract_file = f"contracts/{contract_name}.json"
        contract_json = json.load(open(contract_file, "r"))
        contract = web3.eth.contract(
            address=to_checksum_address(address),
            abi=contract_json['abi'],
        )
        return contract

    @staticmethod
    def deploy_contract(contract_name, args, deployer):
        """
        コントラクトデプロイ
        :param contract_name: コントラクト名
        :param args: コンストラクタに与える引数
        :param deployer: デプロイ実行者
        :return: contract address, ABI, transaction hash
        """
        contract_file = f"contracts/{contract_name}.json"
        contract_json = json.load(open(contract_file, "r"))

        contract = web3.eth.contract(
            abi=contract_json["abi"],
            bytecode=contract_json["bytecode"],
            bytecode_runtime=contract_json["deployedBytecode"],
        )

        tx = contract.constructor(*args).buildTransaction(transaction={'from': deployer, 'gas': 6000000})
        tx_hash, txn_receipt = ContractUtils.send_transaction(transaction=tx)

        contract_address = None
        if txn_receipt is not None:
            # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
            if 'contractAddress' in txn_receipt.keys():
                contract_address = txn_receipt['contractAddress']

        return contract_address, contract_json['abi'], tx_hash

    @staticmethod
    def send_transaction(invoker=None, transaction=None):
        """
        トランザクション送信
        :param invoker: 送信元アドレス
        :param transaction: transaction
        :return: transaction hash, transaction receipt
        """
        if invoker is None:
            web3.personal.unlockAccount(Config.ETH_ACCOUNT, Config.ETH_ACCOUNT_PASSWORD, 60)
        tx_hash = web3.eth.sendTransaction(transaction)
        txn_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
        logger.debug("Send Transaction: tx_hash={}, txn_receipt={}".format(tx_hash.hex(), txn_receipt))
        return tx_hash.hex(), txn_receipt
