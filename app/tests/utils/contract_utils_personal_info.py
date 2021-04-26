# -*- coding: utf-8 -*-

from web3 import Web3
from web3.middleware import geth_poa_middleware

from config import Config
from app.utils import ContractUtils
from app.models import PersonalInfo as PersonalInfoModel
from .account_config import eth_account

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


def register_personal_info(db, invoker: dict, contract_address: str, info: dict, encrypted_info: bytes):
    """名簿用個人情報登録

    :param db: DBセッション
    :param invoker: 実行者
    :param contract_address: コントラクトアドレス
    :param info: 個人情報（生情報）
    :param encrypted_info: 個人情報（暗号化済）
    :return:
    """
    web3.eth.defaultAccount = invoker['account_address']
    PersonalInfoContract = ContractUtils.get_contract('PersonalInfo', contract_address)

    issuer = eth_account['issuer']
    tx_hash = PersonalInfoContract.functions.register(issuer['account_address'], encrypted_info). \
        transact({'from': invoker['account_address'], 'gas': Config.TX_GAS_LIMIT})
    web3.eth.waitForTransactionReceipt(tx_hash)

    # 購入者個人情報TBLにレコードを追加
    record = PersonalInfoModel()
    record.account_address = invoker['account_address']
    record.issuer_address = issuer['account_address']
    record.personal_info = info
    db.session.add(record)
