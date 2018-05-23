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
