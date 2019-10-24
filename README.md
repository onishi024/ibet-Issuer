# 1. 環境構築
## 1-1. 事前準備
* Python3.6.4, Quorum, PostgreSQL 等の環境を整えるために、
 `tmr-sc` と `tmr-node` のReadmeの手順を全て実行しておく。
   1. https://github.com/N-Village/tmr-sc
   2. https://github.com/N-Village/tmr-node

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
* `1-1.「事前準備」`のtmr-scで定義したコントラクトをQuorumにデプロイした時に得られる、コントラクトアドレスを環境変数に定義しておく

例）

```
export TOKEN_LIST_CONTRACT_ADDRESS=0x4e01488325aa068bb66f76003a52f325ef1fdbf7
export PERSONAL_INFO_CONTRACT_ADDRESS=0xc4b4b034133d766e9326d8438656dce16ecd0d23
export PAYMENT_GATEWAY_CONTRACT_ADDRESS=0x2d25d36233c240d067dc19ce9fa782895514d360
export IBET_SB_EXCHANGE_CONTRACT_ADDRESS=0x68888454bfb9355045dd4966434892ea33a971f5
export IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS=0x0be90a91f22e6db59e6c337fc2749ec2f830cac3
export IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS=0x88137aaf6203414d76b0253efb0a168faa0e08ea
export ETH_ACCOUNT_PASSWORD=password
export AGENT_ACCOUNT_PASSWORD=password
export DATABASE_URL=postgresql://issueruser:issueruserpass@localhost:5432/issuerdb
export WEB3_HTTP_PROVIDER=http://localhost:8545
export WEB3_HTTP_PROVIDER_AGENT=http://localhost:8546
export RSA_PASSWORD=password
```
| 環境変数| 意味 | データ取得方法 |
|:----------:|:-----------:|:------------:|
| TOKEN_LIST_CONTRACT_ADDRESS | TokenListコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
| PERSONAL_INFO_CONTRACT_ADDRESS | PersonalInfoコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
| PAYMENT_GATEWAY_CONTRACT_ADDRESS | PaymentGatewayコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
| IBET_SB_EXCHANGE_CONTRACT_ADDRESS | IbetStraightBondExchangeコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
| IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS | IbetCouponExchangeコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
| IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS | IbetMembershipExchangeコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
| ETH_ACCOUNT_PASSWORD | eth.account([0])のパスワード | 初期データ登録時に取得 |
| AGENT_ACCOUNT_PASSWORD | eth.account([0])のパスワード | 初期データ登録時に取得 |
| DATABASE_URL | postgresqlのissuerdbのURL | postgresqlの設定時に取得 |
| WEB3_HTTP_PROVIDER | gethのURL | geth設定から取得 |
| WEB3_HTTP_PROVIDER_AGENT | gethのURL | geth設定から取得 |
| RSA_PASSWORD | キーペアのパスワード | 初回準備で指定したキーペアのパスワード |

- 起動

```
$ cd ibet-Issuer
$ python manage.py runserver [ -h 0.0.0.0 ]
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
python script/INSERT_token.py 3 "IbetStraightBond"
python script/INSERT_token.py 3 "IbetMembership"
python script/INSERT_token.py 3 "IbetCoupon"
```

## 4-2. トークン保有者登録
引数
- 登録件数(int)
- トークン種別(string): IbetStraightBond, IbetMembership, IbetCoupon
- セカンダリー売り注文フラグ(string): 0:売らない, 1:投資家が売り注文を出す
issuerノード・agentノードに接続して実行

```
python script/INSERT_token_holders.py 3 "IbetStraightBond" "0"
python script/INSERT_token_holders.py 3 "IbetMembership" "1"
python script/INSERT_token_holders.py 3 "IbetCoupon" "1"
```

## 4-3. クーポン利用履歴登録
引数
- 登録件数(int)

issuerのノードに接続して実行

```
python script/INSERT_coupon_consume.py 3
```

## 4-4. processor稼働

```
python async/processor_IssueEvent.py
```
