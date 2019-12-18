# 1. 環境構築
## 1-1. 事前準備
* Python3.6.4, Quorum, PostgreSQL 等の環境を整えるために、
 `ibet-SmartContract` と `ibet-Wallet-API` のReadmeの手順を全て実行しておく。
   1. https://github.com/BoostryJP/ibet-SmartContract
   2. https://github.com/BoostryJP/ibet-Wallet-API

## 1-2. 必要なパッケージを取得

```bash
$ cd ibet-Issuer
$ pip install -r requirements.txt
```
- 必要に応じてプロキシオプションや証明書オプションを追加して実行

## 1-3. DBテーブルの構築  
* 事前にデータベースの作成が必要　（例：`issuerdb`）

```bash
$ cd ibet-Issuer
$ python manage.py db init
$ python manage.py db migrate
$ python manage.py db upgrade
```
* 動作確認用データの登録  
* shellに入り、対話モードでデータを登録する

```
$ python manage.py shell
>> （ibet-Issuer/app/tests/testdata.txt にあるコマンドをコピー＆ペースト）
```


# 2. ibet-Issuer の起動確認

## 2-1. 初回準備

* キーペア生成 

```
$ python rsa/create_rsakey.py password
```


* 環境変数追加
* `1-1.「事前準備」`のibet-SmartContractで定義したコントラクトをQuorumにデプロイした時に得られる、コントラクトアドレスを環境変数に定義しておく

例）

```
export TOKEN_LIST_CONTRACT_ADDRESS=0x5bd79b2f9c28597a89b029d555bbc4d3a7c8af1f
export PERSONAL_INFO_CONTRACT_ADDRESS=0x7d4d6d3771de98b4b1975e94faadd5ec13df71f4
export PAYMENT_GATEWAY_CONTRACT_ADDRESS=0x3af11058f0ef4196dae74b55f386405b18545311
export IBET_SB_EXCHANGE_CONTRACT_ADDRESS=0x8dbbdff8640a1c1f64ed185e42433dced09766fd
export IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS=0xc8b3b2e05bcdc10f8fbb17a4f3168f69b32ff85d
export IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS=0x624310d40ee99d93d2b94431e09751e62c04923c
export ETH_ACCOUNT_PASSWORD=password
export AGENT_ACCOUNT_PASSWORD=password
export DATABASE_URL=postgresql://issueruser:issueruserpass@localhost:5432/issuerdb
export WEB3_HTTP_PROVIDER=http://localhost:8545
export WEB3_HTTP_PROVIDER_AGENT=http://localhost:8546
export RSA_PASSWORD=password
```
| 環境変数| 意味 | データ取得方法 |
|:----------:|:-----------:|:------------:|
| TOKEN_LIST_CONTRACT_ADDRESS | TokenListコントラクトのアドレス | ibet-SmartContract/scripts/deploy.shの結果 |
| PERSONAL_INFO_CONTRACT_ADDRESS | PersonalInfoコントラクトのアドレス | ibet-SmartContract/scripts/deploy.shの結果 |
| PAYMENT_GATEWAY_CONTRACT_ADDRESS | PaymentGatewayコントラクトのアドレス | ibet-SmartContract/scripts/deploy.shの結果 |
| IBET_SB_EXCHANGE_CONTRACT_ADDRESS | IbetStraightBondExchangeコントラクトのアドレス | ibet-SmartContract/scripts/deploy.shの結果 |
| IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS | IbetCouponExchangeコントラクトのアドレス | ibet-SmartContract/scripts/deploy.shの結果 |
| IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS | IbetMembershipExchangeコントラクトのアドレス | ibet-SmartContract/scripts/deploy.shの結果 |
| ETH_ACCOUNT_PASSWORD | eth.account([0])のパスワード | 初期データ登録時に取得 |
| AGENT_ACCOUNT_PASSWORD | eth.account([0])のパスワード | 初期データ登録時に取得 |
| DATABASE_URL | postgresqlのissuerdbのURL | postgresqlの設定時に取得 |
| WEB3_HTTP_PROVIDER | gethのURL | geth設定から取得 |
| WEB3_HTTP_PROVIDER_AGENT | gethのURL | geth設定から取得 |
| RSA_PASSWORD | キーペアのパスワード | 初回準備で指定したキーペアのパスワード |

- 起動

```
$ cd ibet-Issuer
$ gunicorn -b localhost:5000 manage:app --config guniconf.py
```
- 接続確認  
http://XXX.XXX.XXX.XXX:5000/ で接続して起動していることを確認。
* 例） localhost:5000
* ログイン画面で、DBに格納されているログインID,パスワードを入力すると、TOP画面が表示される

# 3. テスト実行について
## pytest

* manage.py で定義してあるコマンドオプションにしたがって、テストを実行する

```bash:
$ cd ibet-Issuer
$ python manage.py test
```

testのオプションについては`python manage.py test --help`で確認してください。

# 4. データ増幅スクリプト
## 4-1. トークン登録
引数
- 登録件数(int)
- トークン種別(string):IbetStraightBond, IbetMembership, IbetCoupon


issuerのノードに接続して実行

```
python ./app/tests/script/INSERT_token.py 3 "IbetStraightBond"  
python ./app/tests/script/INSERT_token.py 3 "IbetMembership"
python ./app/tests/script/INSERT_token.py 3 "IbetCoupon"
```

## 4-2. トークン保有者登録
引数
- 登録件数(int)
- トークン種別(string): IbetStraightBond, IbetMembership, IbetCoupon
- セカンダリー売り注文フラグ(string): 0:売らない, 1:投資家が売り注文を出す
issuerノード・agentノードに接続して実行

```
python ./app/tests/script/INSERT_token_holders.py 3 "IbetStraightBond" "0"
python ./app/tests/script/INSERT_token_holders.py 3 "IbetMembership" "1"
python ./app/tests/script/INSERT_token_holders.py 3 "IbetCoupon" "1"
```

## 4-3. クーポン利用履歴登録
引数
- 登録件数(int)

issuerのノードに接続して実行

```
python ./app/tests/script/INSERT_coupon_consume.py 3
```

## 4-4. processor稼働

```
python async/processor_IssueEvent.py
```
