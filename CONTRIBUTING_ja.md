# 開発者ドキュメント（日本語）

## 0. 開発推奨環境

* OS: macOS 10.14 (Mojave)
* PostgreSQL: 10.11

## 1. 環境構築

* PostgreSQLをインストールする

* `issueruser`というユーザを作成し、Databaseを作成する
```
postgres=# CREATE DATABASE issuerdb OWNER issueruser;
CREATE DATABASE
```

* 必要なパッケージを取得
```bash
$ cd ibet-Issuer
$ pip install -r requirements.txt
```

* DB・テーブルのマイグレーション
```bash
$ cd ibet-Issuerk
$ python manage.py db init
$ python manage.py db migrate
$ python manage.py db upgrade
```

## 2. サーバ起動

### 事前準備

* 初期データの登録
```bash
$ python manage.py shell
>> （ibet-Issuer/app/tests/testdata.txt にあるコマンドをコピー＆ペースト）
```

* RSAキーペア生成 
```bash
$ python rsa/create_rsakey.py password
```

### 環境変数追加
* ibet-SmartContractで定義したコントラクトをQuorumにデプロイした時に得られる、コントラクトアドレス等を環境変数に定義しておく

    * TOKEN_LIST_CONTRACT_ADDRESS：TokenListコントラクト
    * PERSONAL_INFO_CONTRACT_ADDRESS：PersonalInfoコントラクト
    * PAYMENT_GATEWAY_CONTRACT_ADDRESS：PaymentGatewayコントラクト
    * IBET_SB_EXCHANGE_CONTRACT_ADDRESS：IbetStraightBondExchangeコントラクト
    * IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS：IbetCouponExchangeコントラクト
    * IBET_MEMBERSHIP_EXCHANGE_CONTRACT_ADDRESS：IbetMembershipExchangeコントラクト
    * ETH_ACCOUNT_PASSWORD：利用アカウントの秘密鍵ファイルのパスワード
    * DATABASE_URL：postgresqlのissuerdbのURL
    * WEB3_HTTP_PROVIDER：Blockchainノードのエンドポイント
    * RSA_PASSWORD：RSAキーペアのパスワード

###  サーバ起動
```bash
$ cd ibet-Issuer
$ gunicorn -b localhost:5000 --reload manage:app --config guniconf.py
```
* http://localhost:5000/ で接続して起動していることを確認
* ログイン画面で、DBに格納されているログインID,パスワードを入力すると、TOP画面が表示される


## 3. テスト実行
* manage.py で定義してあるコマンドオプションにしたがって、テストを実行する
```bash
$ cd ibet-PaymentAgent
$ python manage.py test
```
* testのオプションについては`python manage.py test --help`で確認できる


## 4. データ増幅スクリプト
### トークン登録
* 引数
    - 登録件数(int)
    - トークン種別(string):IbetStraightBond, IbetMembership, IbetCoupon

```bash
python ./app/tests/script/INSERT_token.py 3 "IbetStraightBond"  
python ./app/tests/script/INSERT_token.py 3 "IbetMembership"
python ./app/tests/script/INSERT_token.py 3 "IbetCoupon"
```

### トークン保有者登録
* 引数
    - 登録件数(int)
    - トークン種別(string): IbetStraightBond, IbetMembership, IbetCoupon
    - セカンダリー売り注文フラグ(string): 0:売らない, 1:投資家が売り注文を出す

```bash
python ./app/tests/script/INSERT_token_holders.py 3 "IbetStraightBond" "0"
python ./app/tests/script/INSERT_token_holders.py 3 "IbetMembership" "1"
python ./app/tests/script/INSERT_token_holders.py 3 "IbetCoupon" "1"
```

### クーポン利用履歴登録
* 引数
    - 登録件数(int)

```bash
python ./app/tests/script/INSERT_coupon_consume.py 3
```
