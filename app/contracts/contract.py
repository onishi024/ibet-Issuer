# -*- coding: utf-8 -*-
import json

from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_utils import to_checksum_address

from config import Config

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


class Contract:
    
    def get_contract_info(contract_name):
        contracts = json.load(open('data/contracts.json', 'r'))
        return contracts[contract_name]['abi'], contracts[contract_name]['bytecode'], contracts[contract_name][
            'bytecode_runtime']

    def get_contract(contract_name, address):
        contracts = json.load(open('data/contracts.json', 'r'))
        contract = web3.eth.contract(
            address=to_checksum_address(address),
            abi=contracts[contract_name]['abi'],
        )
        return contract

    def deploy_contract(contract_name, args, deployer):
        contracts = json.load(open('data/contracts.json', 'r'))
        contract = web3.eth.contract(
            abi=contracts[contract_name]['abi'],
            bytecode=contracts[contract_name]['bytecode'],
            bytecode_runtime=contracts[contract_name]['bytecode_runtime'],
        )

        tx_hash = contract.deploy(
            transaction={'from': deployer, 'gas': Config.STRIPE_MAXIMUM_VALUE},
            args=args
        ).hex()

        tx = web3.eth.waitForTransactionReceipt(tx_hash)

        contract_address = ''
        if tx is not None:
            # ブロックの状態を確認して、コントラクトアドレスが登録されているかを確認する。
            if 'contractAddress' in tx.keys():
                contract_address = tx['contractAddress']

        return contract_address, contracts[contract_name]['abi'], tx_hash
