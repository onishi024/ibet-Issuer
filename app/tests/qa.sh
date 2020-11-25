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
# software distributed under the License is distributed onan "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

source ~/.bash_profile

cd /app/ibet-Issuer

mv ./app/tests/data/rsa/test_private.pem ./data/rsa/private.pem
mv ./app/tests/data/rsa/test_public.pem ./data/rsa/public.pem

sleep 10

# test
python manage.py test -v --cov 

status_code=$?

mv coverage.xml ./cov

if [ $status_code -ne 0 ]; then
  exit 1
fi
