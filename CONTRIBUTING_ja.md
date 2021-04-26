# 開発者ドキュメント

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

## 2. 各種設定

### RSAキーペア生成
```bash
$ python manage.py create_rsakey {pass_phrase}
```

### セキュアパラメータ暗号化鍵（SECURE_PARAMETER_ENCRYPTION_KEY）生成
```bash
$ python manage.py create_enckey
```

### 環境変数設定

```
DATABASE_URL = PostgreSQLのissuerアプリ用DBのURL
WEB3_HTTP_PROVIDER = Quorumノードのエンドポイント
RSA_PASSWORD = RSAキーペアのパスワード
SECURE_PARAMETER_ENCRYPTION_KEY = 発行体設定情報のうちセキュアパラメータを暗号化するための共通鍵
```

### ログインユーザの追加
```bash
$ python manage.py create_user {ログインID} {発行体アカウントアドレス}
```

初期パスワードが返却されるので、大切に保管しておく。

### 発行体情報の設定

事前に ibet-SmartContract をデプロイして得られるコントラクトアドレスを data/issuer.yaml に設定する。
issuer.yamlのテンプレートは以下のコマンドで作成することができる。
```bash
$ python manage.py issuer_template > data/issuer.yaml
```

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

記載した内容は、以下のコマンドでDBに反映することができる。
```bash
$ python manage.py issuer_save data/issuer.yaml --eoa-keyfile-password --rsa-privatekey data/rsa/private.pem
```
ここで、`--eoa-keyfile-password`を指定した場合、パスワード入力を求められるので、EOAのkeyfileのパスワードを入力する。
また、`--rsa-privatekey`には上記で作成したRSAの秘密鍵のファイルを指定する。

## 3. サーバ起動
設定が完了したら、以下のコマンドでサーバを起動することができる。
```bash
$ cd ibet-Issuer
$ gunicorn -b localhost:5000 --reload manage:app --config guniconf.py
```
* http://localhost:5000/ で接続して起動していることを確認
* ログイン画面で、DBに格納されているログインID、パスワードを入力すると、TOP画面が表示される


## 4. テスト実行
### テスト実行
* manage.py で定義してあるコマンドオプションにしたがって、テストを実行する
```bash
$ cd ibet-Issuer
$ python manage.py test
```
* testのオプションについては`python manage.py test --help`で確認できる


### データ増幅スクリプト
疎通確認およびテスト用のデータを増幅するためのスクリプトが用意されている。

#### トークン登録
* 引数
    - 登録件数(int)
    - トークン種別(string):IbetStraightBond, IbetMembership, IbetCoupon

```bash
python ./app/tests/script/INSERT_token.py 3 IbetStraightBond
python ./app/tests/script/INSERT_token.py 3 IbetMembership
python ./app/tests/script/INSERT_token.py 3 IbetCoupon
```

#### トークン保有者登録
* 引数
    - 登録件数(int)
    - トークン種別(string): IbetStraightBond, IbetMembership, IbetCoupon

```bash
python ./app/tests/script/INSERT_token_holders.py 3 IbetStraightBond
```

上記を実行後に以下を実行する。

```bash
python batch/processor_IssueEvent.py
python batch/indexer_Transfer.py
```

#### クーポン利用履歴登録
* 引数
    - 登録件数(int)

```bash
python ./app/tests/script/INSERT_coupon_consume.py 3
```

上記を実行後に以下を実行する。

```bash
python batch/processor_IssueEvent.py
python batch/indexer_Transfer.py
python batch/indexer_Consume.py
```

