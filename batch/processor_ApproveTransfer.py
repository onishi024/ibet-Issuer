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
import json
from datetime import datetime
import logging
from logging.config import dictConfig
import os
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import (
    sessionmaker,
    scoped_session
)
from web3 import Web3
from web3.middleware import geth_poa_middleware

path = os.path.join(os.path.dirname(__file__), "../")
sys.path.append(path)

from app.utils import ContractUtils
from app.models import (
    Token,
    IDXTransferApproval,
    TransferApprovalHistory
)
from config import Config

dictConfig(Config.LOG_CONFIG)
log_fmt = "[%(asctime)s] [PROCESSOR-ApproveTransfer] [%(process)d] [%(levelname)s] %(message)s"
logging.basicConfig(format=log_fmt)

web3 = Web3(Web3.HTTPProvider(Config.WEB3_HTTP_PROVIDER))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, echo=False)
db_session = scoped_session(sessionmaker())
db_session.configure(bind=engine)


def get_abi(token: Token):
    return json.loads(token.abi.replace("'", '"').replace('True', 'true').replace('False', 'false'))


while True:
    logging.debug("Loop Start")

    applications_tmp = db_session.query(IDXTransferApproval). \
        filter(IDXTransferApproval.cancelled == None). \
        all()
    applications = []
    for application in applications_tmp:
        transfer_history = db_session.query(TransferApprovalHistory).\
            filter(TransferApprovalHistory.token_address == application.token_address).\
            filter(TransferApprovalHistory.application_id == application.application_id).\
            first()
        if transfer_history is None:
            applications.append(application)

    for application in applications:
        token = db_session.query(Token). \
            filter(Token.token_address == application.token_address). \
            first()
        if token is None:
            logging.warning(f"token not found: {application.token_address}")
            continue

        try:
            TokenContract = web3.eth.contract(
                address=token.token_address,
                abi=get_abi(token)
            )

            # Approve Transfer
            now = str(datetime.utcnow().timestamp())
            approve_tx = TokenContract.functions.approveTransfer(application.application_id, now). \
                buildTransaction({"from": token.admin_address, "gas": Config.TX_GAS_LIMIT})
            tx_hash, txn_receipt = ContractUtils.send_transaction(
                transaction=approve_tx,
                eth_account=token.admin_address,
                db_session=db_session
            )
            transfer_approve_history = TransferApprovalHistory()
            transfer_approve_history.token_address = application.token_address
            transfer_approve_history.application_id = application.application_id

            if txn_receipt["status"] == 1:  # Success
                transfer_approve_history.result = 1
                logging.debug(f"Transfer approved: "
                              f"token_address = {application.token_address}, "
                              f"application_id = {application.application_id}")
            else:  # Fail
                # Cancel Transfer
                cancel_tx = TokenContract.functions.cancelTransfer(application.application_id, now). \
                    buildTransaction({"from": token.admin_address, "gas": Config.TX_GAS_LIMIT})
                tx_hash, txn_receipt = ContractUtils.send_transaction(
                    transaction=cancel_tx,
                    eth_account=token.admin_address,
                    db_session=db_session
                )
                transfer_approve_history.result = 2  # Error
                logging.error(f"Transfer was canceled: "
                              f"token_address = {application.token_address}, "
                              f"application_id = {application.application_id}")
            db_session.commit()
        except Exception as err:
            logging.exception(err)
            logging.error(f"Process failed: "
                          f"token_address = {application.token_address}, "
                          f"application_id = {application.application_id}")
            continue

    logging.debug("Loop Finished")
    time.sleep(10)
