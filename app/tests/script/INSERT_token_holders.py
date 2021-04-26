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

import os
import argparse
import time

import sys

from web3 import Web3
from web3.middleware import geth_poa_middleware

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

path = os.path.join(os.path.dirname(__file__), "../../..")
sys.path.append(path)

from app.utils import ContractUtils
from app.models import Token, Issuer
from config import Config

# 設定
WEB3_HTTP_PROVIDER = os.environ.get('WEB3_HTTP_PROVIDER')
web3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

# DB接続定義
URI = os.environ.get("DATABASE_URL") or 'postgresql://issueruser:issuerpass@localhost:5432/issuerdb'
engine = create_engine(URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)


def issue_token(token_type, amount, issuer):
    """
    トークン発行
    ISSUERが実行
    :param token_type: トークン種別
    :param amount: 発行数量
    :param issuer: 発行体
    :return: トークンアドレス、ABI
    """
    # トークン属性の設定
    arguments = []
    template_id = None
    if token_type == 'IbetStraightBond':
        arguments = [
            'TEST_TOKEN',  # 名称
            'TEST',  # 略称
            amount,  # 発行数量
            100,  # 額面
            '20221231',  # 償還日
            100,  # 償還金額
            '20201231',  # 特典付与日
            '特典内容',  # 特典内容
            '発行目的',  # 発行目的
        ]
        template_id = Config.TEMPLATE_ID_SB
    elif token_type == 'IbetMembership':
        arguments = [
            'TEST_TOKEN',  # 名称
            'TEST',  # 略称
            amount,  # 発行数量
            '0x0000000000000000000000000000000000000000',  # DEXコントラクト
            '会員権詳細',  # 会員権詳細
            '特典詳細',  # 特典詳細
            '20181010',  # 有効期限
            'メモ',  # メモ
            True,  # 譲渡可能
            '問い合わせ先',  # 問い合わせ先
            'プライバシーポリシー'  # プライバシーポリシー
        ]
        template_id = Config.TEMPLATE_ID_MEMBERSHIP
    elif token_type == 'IbetCoupon':
        arguments = [
            'TEST_TOKEN',  # 名称
            'TEST',  # 略称
            amount,  # 発行数量
            '0x0000000000000000000000000000000000000000',  # DEXコントラクト
            '会員権詳細',  # クーポン詳細
            '特典詳細',  # 特典詳細
            'メモ',  # メモ
            '20181010',  # 有効期限
            True,  # 譲渡可能
            '問い合わせ先',  # 問い合わせ先
            'プライバシーポリシー'  # プライバシーポリシー
        ]
        template_id = Config.TEMPLATE_ID_COUPON
    elif token_type == 'IbetShare':
        arguments = [
            'TEST_TOKEN',  # 名称
            'TEST',  # 略称
            '0x0000000000000000000000000000000000000000',  # DEXコントラクト
            '0x0000000000000000000000000000000000000000',  # 個人情報コントラクト
            100,  # 発行価格
            amount,  # 発行数量
            10,  # １株配当
            '20221231',  # 権利確定日
            '20221231',  # 配当支払日
            '20221231',  # 消却日
            '問い合わせ先',  # 問い合わせ先
            'プライバシーポリシー',  # プライバシーポリシー
            'メモ',  # 補足情報
            True,  # 譲渡可能
        ]
        template_id = Config.TEMPLATE_ID_SHARE

    _, bytecode, bytecode_runtime = ContractUtils.get_contract_info(token_type)
    contract_address, abi, tx_hash = ContractUtils.deploy_contract(
        token_type, arguments, issuer.eth_account, db_session=db_session)

    # DB登録
    token = Token()
    token.template_id = template_id
    token.tx_hash = tx_hash
    token.admin_address = issuer.eth_account.lower()
    token.token_address = None
    token.abi = str(abi)
    token.bytecode = bytecode
    token.bytecode_runtime = bytecode_runtime
    db_session.merge(token)
    db_session.commit()

    return {'address': contract_address, 'abi': abi}


def bulk_transfer(token_contract, number, issuer):
    """
    一括移転
    :param token_contract: トークンコントラクト
    :param number: 増幅件数
    :param issuer: 発行体
    :return: なし
    """
    for i in range(number):
        print(i)
        tx = token_contract.functions.transferFrom(issuer.eth_account, web3.eth.accounts[i], 1). \
            buildTransaction({'from': issuer.eth_account, 'gas': Config.TX_GAS_LIMIT})
        ContractUtils.send_transaction(transaction=tx, eth_account=issuer.eth_account, db_session=db_session)


def main(number, token_type, issuer):
    """
    Main処理
    :param number: 増幅件数
    :param token_type: トークン種別
    :param issuer: 発行体
    :return:
    """

    # トークン発行
    amount = number  # 登録件数分のトークンを発行する
    token = issue_token(token_type, amount, issuer)
    token_contract = ContractUtils.get_contract(token_type, token['address'])

    # processorがトークンをDBに登録する前に移転してしまうとindexer_Transferが機能しなくなる。
    # （デプロイ〜トークンDB登録の間にある移転イベントを見逃す。）
    # processor_IssueEventによりDB登録されるまで待つ。
    time.sleep(12)

    # トークン移転
    bulk_transfer(token_contract, number, issuer)


#############################
# Main
#############################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Token保有者の増幅スクリプト")
    parser.add_argument("number", type=int, help="登録件数")
    parser.add_argument("token_type", type=str, help="IbetStraightBond, IbetMembership, IbetCoupon")
    parser.add_argument("--issuer", '-s', type=str, help="発行体アドレス")
    args = parser.parse_args()

    if not args.number:
        raise Exception("増幅件数は必須です")

    if args.number > 10:
        raise Exception("増幅件数は10件までです")

    if not args.token_type:
        raise Exception("IbetStraightBond, IbetMembership, IbetCoupon")

    issuer_address = args.issuer if args.issuer is not None else web3.eth.accounts[0]
    issuer_model = db_session.query(Issuer).filter(Issuer.eth_account == issuer_address).first()
    if issuer_model is None:
        raise Exception("発行体が未登録です")
    print(f'発行体アドレス: {issuer_model.eth_account}')

    main(args.number, args.token_type, issuer_model)
