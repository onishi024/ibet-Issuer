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
- 初回準備
    - キーペア生成 `./rsa/run.sh password`
    - 環境変数追加

例）
```
export TOKEN_LIST_CONTRACT_ADDRESS=0x4e01488325aa068bb66f76003a52f325ef1fdbf7
export PERSONAL_INFO_CONTRACT_ADDRESS=0xc4b4b034133d766e9326d8438656dce16ecd0d23
export WHITE_LIST_CONTRACT_ADDRESS=0x2d25d36233c240d067dc19ce9fa782895514d360
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
| WHITE_LIST_CONTRACT_ADDRESS | WhiteListコントラクトのアドレス | tmr-sc/deploy/deploy.shの結果 |
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
python script/INSERT_token.py 3 "IbetStraightBond"
python script/INSERT_token.py 3 "IbetMembership"
python script/INSERT_token.py 3 "IbetCoupon"
```

### ２．トークン保有者登録
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

### ３．クーポン利用履歴登録
引数
- 登録件数(int)

issuerのノードに接続して実行

```
python script/INSERT_coupon_consume.py 3
```

### ４. processor稼働

```
python async/processor_IssueEvent.py
```