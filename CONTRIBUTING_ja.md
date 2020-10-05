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
$ cd ibet-Issuer
$ python manage.py db init
$ python manage.py db migrate
$ python manage.py db upgrade
```

## 2. サーバ起動

### 事前準備

* RSAキーペア生成
```bash
$ python rsa/create_rsakey.py password
```

* EOA keyfileパスワード保管用の鍵生成
```bash
$ python manage.py eth_account_password_secret_key
```

* 環境変数追加
    * DATABASE_URL：postgresqlのissuerdbのURL
    * WEB3_HTTP_PROVIDER：Quorumノードのエンドポイント
    * RSA_PASSWORD：RSAキーペアのパスワード
    * ETH_ACCOUNT_PASSWORD_SECRET_KEY: EOA keyfile のパスワード（AES鍵）を二重で暗号化して保管するための共通鍵

* 初期ユーザの追加
```bash
$ python manage.py create_user {発行体アカウントアドレス}
```

* 発行体の設定
```bash
$ python manage.py issuer_template > data/issuer.yaml
```

事前に ibet-SmartContract をデプロイして得られるコントラクトアドレスを data/issuer.yaml に設定する。
```yaml
eth_account: '{発行体アカウントアドレス}'
issuer_name: ''
private_keystore: GETH
network: IBET
max_sell_price: 100000000
agent_address: ''
payment_gateway_contract_address: '{PaymentGatewayコントラクト}'
personal_info_contract_address: '{PersonalInfoコントラクト}'
token_list_contract_address: '{TokenListコントラクト}'
ibet_share_exchange_contract_address: '{IbetOTCExchangeコントラクト}'
ibet_sb_exchange_contract_address: '{IbetStraightBondExchangeコントラクト}'
ibet_membership_exchange_contract_address: '{IbetMembershipExchangeコントラクト}'
ibet_coupon_exchange_contract_address: '{IbetCouponExchangeコントラクト}'
```

記載した内容をDBに登録する。
パスワード入力を求められるのでGethの発行体アカウントパスワード（keyfileパスワード）を入力する。
```bash
$ python manage.py issuer_save data/issuer.yaml --eoa-keyfile-password --rsa-privatekey data/rsa/private.pem
```

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
$ cd ibet-Issuer
$ python manage.py test
```
* testのオプションについては`python manage.py test --help`で確認できる


## 4. データ増幅スクリプト
### トークン登録
* 引数
    - 登録件数(int)
    - トークン種別(string):IbetStraightBond, IbetMembership, IbetCoupon

```bash
python ./app/tests/script/INSERT_token.py 3 IbetStraightBond
python ./app/tests/script/INSERT_token.py 3 IbetMembership
python ./app/tests/script/INSERT_token.py 3 IbetCoupon
```

### トークン保有者登録
* 引数
    - 登録件数(int)
    - トークン種別(string): IbetStraightBond, IbetMembership, IbetCoupon

```bash
python ./app/tests/script/INSERT_token_holders.py 3 IbetStraightBond
```

上記を実行後に以下を実行する。

```bash
python async/processor_IssueEvent.py
python async/indexer_Transfer.py
```

### クーポン利用履歴登録
* 引数
    - 登録件数(int)

```bash
python ./app/tests/script/INSERT_coupon_consume.py 3
```

上記を実行後に以下を実行する。

```bash
python async/processor_IssueEvent.py
python async/indexer_Transfer.py
python async/indexer_Consume.py
```

