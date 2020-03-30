# -*- coding:utf-8 -*-
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
