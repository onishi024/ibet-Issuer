# ibet for issuer

## 前準備
- python3.6.3の環境構築  
`conda create`などでpython3.6.3の環境を準備してください。

- 必要なパッケージの取得  
```bash
cd tmr-issuer
pip install -r requirements.txt
```
必要に応じてプロキシオプションや証明書オプションを追加して実行してください。

- DBテーブルの構築  
事前にデータベースを作成しておいてください。（例：issuerdb）

```bash
cd tmr-issuer
python manage.py db init
python manage.py db migrate
python manage.py db upgrade
```
- 動作確認用データの登録  
*tmr-issuer/app/tests/testdata.txt* のコマンドをベースに  
`python manage.py shell`  
で対話モードでデータを登録してください。

## ibet:issuerの起動確認
- 起動

```bash
cd tmr-issuer
python manage.py runserver -h 0.0.0.0
```
- 接続確認  
あとは http://XXX.XXX.XXX.XXX:5000/ で接続してください。

## テスト実行について
### pytest

```bash
cd tmr-issuer
python manage.py test
```

testのオプションについては`python manage.py test --help`で確認してください。

## データ増幅スクリプト
### １．トークン登録
引数
- 登録件数(int)
- トークン種別(string):IbetStraightBond, IbetMembership, IbetCoupon


issuerのノードに接続して実行

```
export DATABASE_URL=postgresql://issueruser:issueruserpass@172.16.239.2:5432/issuerdb
export WEB3_HTTP_PROVIDER=http://172.16.239.10:8545
export ETH_ACCOUNT_PASSWORD=nvillage201803+
export TOKEN_LIST_CONTRACT_ADDRESS=0x8e55f8cd1bf13dad83bfe91344feec60f70fd280
export IBET_SB_EXCHANGE_CONTRACT_ADDRESS=0xd85a292e77628e4027250d46abaeeac1d3d192b5
export IBET_CP_EXCHANGE_CONTRACT_ADDRESS=0x601be715b01ebe56af3518b1e98341668a35798e
export IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS=0x2b46c5ea536914f22998cdfe6a9bbf2d63e6e6b1

python script/INSERT_token.py 3 "IbetStraightBond"
python script/INSERT_token.py 3 "IbetMembership"
python script/INSERT_token.py 3 "IbetCoupon"
```

### ２．トークン保有者登録
引数
- 登録件数(int)
- トークン種別(string): IbetStraightBond, IbetMembership, IbetCoupon
- セカンダリー売り注文フラグ(string): 0:売らない, 1:投資家が売り注文を出す
issuerのノードに接続して実行

```
export DATABASE_URL=postgresql://issueruser:issueruserpass@172.16.239.2:5432/issuerdb
export WEB3_HTTP_PROVIDER=http://172.16.239.10:8545
export ETH_ACCOUNT_PASSWORD=nvillage201803+
export TOKEN_LIST_CONTRACT_ADDRESS=0x8e55f8cd1bf13dad83bfe91344feec60f70fd280
export PERSONAL_INFO_CONTRACT_ADDRESS=0x1378ed51e8d6d7aa42862ce2d0497a2cca1bd2ff
export WHITE_LIST_CONTRACT_ADDRESS=0x419d3c7461a97ccbecf2153d0195497260b48d9e
export IBET_SB_EXCHANGE_CONTRACT_ADDRESS=0xd85a292e77628e4027250d46abaeeac1d3d192b5
export IBET_CP_EXCHANGE_CONTRACT_ADDRESS=0x601be715b01ebe56af3518b1e98341668a35798e
export IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS=0x2b46c5ea536914f22998cdfe6a9bbf2d63e6e6b1

python script/INSERT_token_holders.py 3 "IbetStraightBond" "0"
python script/INSERT_token_holders.py 3 "IbetMembership" "1"
python script/INSERT_token_holders.py 3 "IbetCoupon" "1"
```

### ３．クーポン利用履歴登録
引数
- 登録件数(int)

issuerのノードに接続して実行

```
export DATABASE_URL=postgresql://issueruser:issueruserpass@172.16.239.2:5432/issuerdb
export WEB3_HTTP_PROVIDER=http://172.16.239.10:8545
export ETH_ACCOUNT_PASSWORD=nvillage201803+
export TOKEN_LIST_CONTRACT_ADDRESS=0x8e55f8cd1bf13dad83bfe91344feec60f70fd280
export PERSONAL_INFO_CONTRACT_ADDRESS=0x1378ed51e8d6d7aa42862ce2d0497a2cca1bd2ff
export WHITE_LIST_CONTRACT_ADDRESS=0x419d3c7461a97ccbecf2153d0195497260b48d9e
export IBET_CP_EXCHANGE_CONTRACT_ADDRESS=0x601be715b01ebe56af3518b1e98341668a35798e

python script/INSERT_coupon_consume.py 3
```
