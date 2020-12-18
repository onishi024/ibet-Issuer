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

import base64
import json

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP

if __name__ == "__main__":

    personal_info_json = {
        "name": "ブーストリー太郎",
        "address": {
            "postal_code": "1010032",
            "prefecture": "東京都",
            "city": "千代田区",
            "address1": "岩本町３丁目９—２",
            "address2": "ＰＭＯ岩本町 4F"
        },
        "email": "abcd1234@boostry.co.jp",
        "birth": "20191102"
    }

    key = RSA.importKey(open('data/rsa/public.pem').read())
    cipher = PKCS1_OAEP.new(key)

    encrypted_info = base64.encodebytes(
        cipher.encrypt(json.dumps(personal_info_json).encode('utf-8'))
    )

    print(encrypted_info.decode('utf-8'))
