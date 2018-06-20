# coding=utf-8
from Crypto.PublicKey import RSA
from Crypto import Random

def create(passphrase)
    random_func = Random.new().read
    rsa = RSA.generate(1024, random_func)

    # 秘密鍵作成
    private_pem = rsa.exportKey(format='PEM', passphrase=passphrase)
    with open('private.pem', 'w') as f:
        f.write(private_pem)

    # 公開鍵作成
    public_pem = rsa.publickey().exportKey()
    with open('public.pem', 'w') as f:
        f.write(public_pem)

if __name__ == '__main__':
    
    create(passphrase)
