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

source ~/.bash_profile

cd /app/ibet-Issuer

# batch
python batch/processor_IssueEvent.py &
python batch/processor_BatchTransfer.py &
python batch/processor_BondLedger_JP.py &
python batch/processor_ApproveTransfer.py &
python batch/indexer_Transfer.py &
python batch/indexer_TransferApproval.py &
python batch/indexer_ApplyFor.py &
python batch/indexer_Consume.py &
python batch/indexer_Order.py &
python batch/indexer_Agreement.py &
python batch/indexer_PersonalInfo.py &

#run server
gunicorn -b 0.0.0.0:5000 --reload manage:app --config guniconf.py
