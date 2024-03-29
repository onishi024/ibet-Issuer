#!/bin/bash

# Copyright BOOSTRY Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

PROC_LIST="${PROC_LIST} batch/indexer_Agreement.py"
PROC_LIST="${PROC_LIST} batch/indexer_ApplyFor.py"
PROC_LIST="${PROC_LIST} batch/indexer_Consume.py"
PROC_LIST="${PROC_LIST} batch/indexer_Order.py"
PROC_LIST="${PROC_LIST} batch/indexer_PersonalInfo.py"
PROC_LIST="${PROC_LIST} batch/indexer_Transfer.py"
PROC_LIST="${PROC_LIST} batch/indexer_TransferApproval.py"
PROC_LIST="${PROC_LIST} batch/processor_BatchTransfer.py"
PROC_LIST="${PROC_LIST} batch/processor_BondLedger_JP.py"
PROC_LIST="${PROC_LIST} batch/processor_IssueEvent.py"
PROC_LIST="${PROC_LIST} batch/processor_ApproveTransfer.py"

for i in ${PROC_LIST}; do
  # shellcheck disable=SC2009
  ps -ef | grep -v grep | grep "$i"
  if [ $? -ne 0 ]; then
    exit 1
  fi
done

curl -D - -s -o /dev/null http://127.0.0.1:5000/auth/login | grep "HTTP/1.1 200 OK"
