# -*- coding: utf-8 -*-
from web3 import Web3
from web3.middleware import geth_poa_middleware
from config import Config
from app.models import Token
from logging import getLogger

logger = getLogger('api')
web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)


# 発行済みトークンのアドレスをDBへ登録
def processor_issue_event(db):
    # コントラクトアドレスが登録されていないTokenの一覧を抽出
    tokens = Token.query.all()
    for token in tokens:
        if token.token_address is None:
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
