# -*- coding:utf-8 -*-
import pytest
import os
import time

from .conftest import TestBase
from .account_config import eth_account
from config import Config
from .contract_modules import *
from ..models import Token

from logging import getLogger
logger = getLogger('api')

class TestToken(TestBase):
    issuer_encrypted_info = 'hekR0bz6qfsnaIYLZ7emUNaynqHFQsrwehcMq8r0tw2SRSM2vhb4B9HZWNaB0pOF7Obtp6qQM59ADfpwoGw3KewOw/4ZmPG7ajFaDYP1CHwz+LaxcQciJDi07ROZYDKwxukbGVcRxWwRJdjt9fOjLJzcgEyTG44LqxAjaGANVQnf3ZF3I6iZ84FrDKTGQ/86Qzv/Mj53nGkU053J6p8/RWU3n1vOtwOOMSwqc2gZlCEMqjjKxkkFUxbVZAFXNMiLgOAsnvBsq49Tr0J4ei0M+j4uWnbxsB2mMdKJTY69jiCOgiTa/of//W9H/jl0PzTINXb59xLTDuER8Ni7UYCU2MIcWzsQY6+2kzpkSglqG3JXB/iQjg+TZUXgeRIVZvo1uecdKRegJbcNt/xn1HH1FzO6kxmcHP/GML5Hh0AXwswkzdDhJZExWYVJ6+W8Uc/OlO1Y1SzScX7I7f7WcsDgPrxuV+oVWl/e+bBroi6UAJAappq17n5ZxGB9vgDb4tQLXCV/hyyo61O4hg8Ca7jH2imxN4612e/Z5ZrZPQf9rnMJXLPF57r1lECC2xvfjTdhEmBblO1ynY/hlgW7mscgrZDMfr/shsdrQyqH1yExAmN9puR2X96Ejqn+lRBbhi9kqxAAnP1G4S3S9EDgMc1yiCmq4mLVZO/SyCbKzytXOmScMHWyPmcjfjt+uuxkWM6NifUkeWcc3NjXLDjwj1ipuegJJnVoAje950w3HEWBzxX2W16EHlzEdovXGObtV8WP/p+Q/WesPyE9s1gh/ND19APBQx7+TR7LepCTOA1cmFl/JTFFk37dGRka34CTDjqF+kan0sk/JPGytbmLMWEbZiZkDhcZ8kTI9EpTYeS4se5B3X4Nd/Fi6k/kGSK0FtYakwmc0q30eWnDyE049MmdZQV/QdARCrNWipv1WRbL5oNlP9pbR8Mz3pMcISofLdyrWtdJCgj1sNj/CXFai+4F2ce5wQZb95kCyrN0AT2zj8JAuZImeTDDUQpnn++iMGWkWKYPnRaw5Jel9OcYKbgsqvSyzTzSgfWvUMZxD0Fz6SLOeGKvWDlSDVi/jFOZZxWy4EYElBklc47eehlMQHGQT/6PZVnZbuf43j1EF8+s4VMLf7nnb1JG6tQ2gTYx/UG+arK25f5ZXnzaOQNX5X2Hu/Bv/s1PmaXa1QcEIuByumNFra7iNnhT/6DTgNAVPlbTUbTLrc+8kVft2VDIe1FUG4UNjpDGjP/j/Ovjy3prMrWdBAXcLvRuVk9NMiMa4qQIuVE+Dd4hw+47At8LIfu6pCwiX5cRPCCVEzZ5I8il41qbvdIjQ2ewANB0j1Ve3hrbUQcZcF/MMKGPHwRDaAprQ9oZZVX+pVrcZmD/EQr9A0NvRhvcQb1JdOIaOyWnMfj0r3Ki0eIp2seLtqQ9Mpxje+plCqHfy5FXunLMi3U5FzTLkPmt5ANiNtE5E9X6hqzBgSW4dR+plJbrsE0JvmNFxefiN2tTj9QOuOKy2QXdc3oR79Mi4KKKdti2sS6wopX8kkMSzK+LZ8Fr98FeKX/uLXj1T4o7xb65HG3i45kDhv5cGilkNyI8euOsEsMlfQbboITQpcRhspzunJXfHx9sEpiVjFL+vMR/vcNblJ3zZUtiOoqeQEynH7paCa2vxURLeJ3PsmfowIO8ZebX+ZWM8ElpNIG0l43SxoGFUP/tI78='
    trader_encrypted_info = 'Upu+PwVJUYV30KMTrrDwEHTT/u6Px+5VdRWx+FZdKuJ/36TvIBJEsyf4bv/dgZwcOoBztWQnQ71Cf55fBkopqjpHm7YJpeRnEdqRVwOc44PynVdcZeQvWizU867ub5QUh/coG5ftCB5ln3UcunEMbxmOLpjnTmNSRdIz0iWdYU/gxFuHNVxexTgSpvhUp4R7QrY/mBp5g6reYILCjy9wabJ8i7iSEOjP5szmtmCDIqhBnidtmoVxfgDGUDYpL3HU8HmfDIwCc+YuUORS3LSBVWshEK9EO89flghnI/wozsh7vntcGXKfNkVkfwZx9C0q878+Ep+p6pFpU4HMGbjTEtFsozEjZT22wAMfMDZOoBOsrURM0PGom6bJ/zfrAKr9oAWgjvBkaYLknxagwOosVLQH/QF31mlQyFScXJEISsi023S7l/nDJ3DVPS8ejghWgvAUcfwOSA7Vt9fS2KLUTUbd+RTd4FL9uks+A3rm0yL2Jc/Px4fpbnENBrenqSyBl1sYw7JLvvfut/hz6qUiOswoy2G0tZszKGo9nZiOMkmAr5sv2xh4M380uG8KOf3PaZXm6elFPqCOilHAZpQfydA1y1M7QgVIa+WkO53HevVUn9iqk/u6q5x3xA3HgneiZFGXWCzJwnV+GMkR0ILGbugkP5bl/nlji/grev40jEdWlVy2tazHwh+2fH6QBTWfiTVvrPTcprWy0GAjqAwPyCuCkMcjr9invpkuwaI7BugbAyWA8o1ANv35hinVnNtpgbesJjHxJWlbE7x4Ph+Big2W5o+DdZpnIYFtBOi6YdB50lvemFcktFUewCRzzB5cO3wgkvpxkgPGpy3mq0GSB7gJqmJ28RVjjOyNCmbVsl0V3Sgq3YhpfIyeoFZ8YQCz+m8QXXEDUeLdkms2yKmaIYZqinXgRNxaQdwdgxbYYyamf9Ena3E+KeLuHSOq3xtupgHopv2Y6c1/hBznKy6gVJVbfEMYRWYqUM7KYLZahcaLvFP8YuD7nTx7r6tKH6OaQi12FO+Pnk98kvG66VWM+i/AlWvNSI+3Cx50sDW5BF7Rl9DNB59AfX7Ur7Pdn7lfDTy6fDLqGs+LtmYUOtt8YlL6mAmH1x7pV5nF+01CnaShAC430cQyBB2vngs/p4FS654z0dIkEZ6YLSCIBIJpNYJY2oGOixNTrG+4lECKyQ0HY4AmtXnH5iqgS9/NCcLHHBWiqIXQgCQ5sCUVTIe0cHu6fWLrDtAlBncrX/6gEix0N/O6OQHfVx3veHRYGMJ1ZIM25gqI/ccgz9IyKtG//8zGqruvt6y8e6xJ7yh3OnSHPbNmLd8hcY9Ti2gQnMbKe2hDFQJehLRawNG8Yujd0H3ROnypEaCF2m7hKy23w3vmeVnPMM6xYshCsjXInjjiXn8xLof5NUA9Ea8d2U/3DaGPm4Xgt9VV0hilTKAKRQsSSG9YBrg6iGI6IKnka3tD7iKOvsBahZstNw4xEn7NifYPatCJjHDKaSqeqrdS9U9T0ClnG4iD5U8ufIEtvHKewDMOpVD6KW/lszilrziA6hSUyVPBx/p/VHhhAXXJ8ISvk+TLrpRvUukE4CtwqE/rdryeBvYM7XKqnqV72zOlirnlx2iiaQWm6XfSGdfjaUt2J5VSbwHv5lv534CCWrqBC7V/X9KISx1UV0regXvOtOen2UV2xshEv2ljrWjGPFY='
    url_tokenlist = '/token/tokenlist' # 発行済債券一覧
    url_positions = '/token/positions' # 保有債券一覧 
    url_issue = '/token/issue' # 債券新規発行
    url_setting = '/token/setting/' # 設定画面
    url_sell = 'token/sell/' # 募集画面
    url_cancel_order = 'token/cancel_order/' # 募集停止
    url_release = 'token/release' # リリース
    url_holders = 'token/holders/' # 債券保有者一覧
    url_holder = 'token/holder/' # 債券保有者詳細 
    url_signature = 'token/request_signature/' # 認定依頼


    # ＜正常系1＞
    # 発行済債券一覧の参照(0件)
    def test_normal_1(self, app, shared_contract):
        # Config設定は1_1で全て実施
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetStraightBondExchange']['address']
        Config.WHITE_LIST_CONTRACT_ADDRESS = shared_contract['WhiteList']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']

        # 発行済債券一覧
        client = self.client_with_admin_login(app)
        response = client.get(self.url_tokenlist)
        assert response.status_code == 200
        assert '<title>発行済債券一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2＞
    # 保有債券一覧(0件)
    def test_normal_2(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>保有債券一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系3＞
    # 新規発行　→　DB登録処理 →　詳細画面
    def test_normal_3(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テスト債券',
                'symbol': 'BOND',
                'totalSupply': 1000000,
                'faceValue': 1000,
                'interestRate': 1000,
                'interestPaymentDate1': '0101',
                'interestPaymentDate2': '0201',
                'interestPaymentDate3': '0301',
                'interestPaymentDate4': '0401',
                'interestPaymentDate5': '0501',
                'interestPaymentDate6': '0601',
                'interestPaymentDate7': '0701',
                'interestPaymentDate8': '0801',
                'interestPaymentDate9': '0901',
                'interestPaymentDate10': '1001',
                'interestPaymentDate11': '1101',
                'interestPaymentDate12': '1201',
                'redemptionDate': '20191231',
                'redemptionAmount': 10000,
                'returnDate': '20191231',
                'returnAmount': '商品券をプレゼント',
                'purpose': '新商品の開発資金として利用。',
                'memo': 'メモ'
            }
        )
        assert response.status_code == 302

        # 2秒待機
        time.sleep(2)

        # DB登録処理
        processorIssueEvent(db)

        # 設定画面
        token = Token.query.get(1)
        response = client.get(self.url_setting + token.token_address)
    
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '1000000'.encode('utf-8') in response.data
        assert '1000'.encode('utf-8') in response.data
        assert '0101'.encode('utf-8') in response.data
        assert '0201'.encode('utf-8') in response.data
        assert '0301'.encode('utf-8') in response.data
        assert '0401'.encode('utf-8') in response.data
        assert '0501'.encode('utf-8') in response.data
        assert '0601'.encode('utf-8') in response.data
        assert '0701'.encode('utf-8') in response.data
        assert '0801'.encode('utf-8') in response.data
        assert '0901'.encode('utf-8') in response.data
        assert '1001'.encode('utf-8') in response.data
        assert '1101'.encode('utf-8') in response.data
        assert '1201'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '10000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '商品券をプレゼント'.encode('utf-8') in response.data
        assert '新商品の開発資金として利用。'.encode('utf-8') in response.data
        assert 'メモ'.encode('utf-8') in response.data

    # ＜正常系4＞
    # 発行済債券一覧の参照(1件)
    def test_normal_4(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_tokenlist)
        assert response.status_code == 200
        assert '<title>発行済債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data

    # ＜正常系5＞
    # 保有債券一覧(1件)
    def test_normal_5(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>保有債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data

    # ＜正常系6＞
    # 新規募集画面の参照
    def test_normal_6(self, app, shared_contract):
        token = Token.query.get(1)
        client = self.client_with_admin_login(app)
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>債券新規募集'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '1000000'.encode('utf-8') in response.data
        assert '1000'.encode('utf-8') in response.data
        assert '0101'.encode('utf-8') in response.data
        assert '0201'.encode('utf-8') in response.data
        assert '0301'.encode('utf-8') in response.data
        assert '0401'.encode('utf-8') in response.data
        assert '0501'.encode('utf-8') in response.data
        assert '0601'.encode('utf-8') in response.data
        assert '0701'.encode('utf-8') in response.data
        assert '0801'.encode('utf-8') in response.data
        assert '0901'.encode('utf-8') in response.data
        assert '1001'.encode('utf-8') in response.data
        assert '1101'.encode('utf-8') in response.data
        assert '1201'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '10000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '商品券をプレゼント'.encode('utf-8') in response.data
        assert '新商品の開発資金として利用。'.encode('utf-8') in response.data
        assert 'メモ'.encode('utf-8') in response.data

    # ＜正常系7＞
    # 募集 → personinfo登録 → 募集 → whitelist登録 →
    # 募集 → 保有債券一覧で確認
    def test_normal_7(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        token = Token.query.get(1)
        url_sell = self.url_sell + token.token_address
        # 募集
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302
        # 保有債券一覧でエラーを確認
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '法人名、所在地の情報が未登録です。'.encode('utf-8') in response.data
        
        # personalinfo登録
        register_personalinfo(eth_account['issuer'], shared_contract['PersonalInfo'], self.issuer_encrypted_info)
        # 募集
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302
        # 保有債券一覧でエラーを確認
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '金融機関の情報が未登録です。'.encode('utf-8') in response.data
        
        # whitelist登録
        register_whitelist(eth_account['issuer'], shared_contract['WhiteList'], self.issuer_encrypted_info)
        # 募集
        response = client.post(
            url_sell,
            data={
                'sellPrice': 100,
            }
        )
        assert response.status_code == 302

        # 待機（募集には時間がかかる）
        time.sleep(5)

        # 保有債券一覧
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>保有債券一覧'.encode('utf-8') in response.data
        assert '新規募集を受け付けました。募集開始までに数分程かかることがあります。'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '募集停止'.encode('utf-8') in response.data

    # ＜正常系8＞
    # 募集停止 → 保有債券一覧で確認
    def test_normal_8(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_cancel_order + '0',
        )
        assert response.status_code == 302

        # 待機
        time.sleep(2)

        # 保有債券一覧
        response = client.get(self.url_positions)
        assert response.status_code == 200
        assert '<title>保有債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data
        assert '募集開始'.encode('utf-8') in response.data

    # ＜正常系9＞
    # 募集設定　画像URL登録 → 詳細画面で確認
    def test_normal_9(self, app, shared_contract):
        token = Token.query.get(1)
        url_setting = self.url_setting + token.token_address
        client = self.client_with_admin_login(app)
        # 募集設定
        response = client.post(
            url_setting,
            data={
                'image_small': 'https://test.com/image_small.jpg',
                'image_medium': 'https://test.com/image_medium.jpg',
                'image_large': 'https://test.com/image_large.jpg',
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(6)

        # 債券詳細設定
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'https://test.com/image_small.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_medium.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_large.jpg'.encode('utf-8') in response.data

    # ＜正常系10＞
    # 公開
    def test_normal_10(self, app, shared_contract):
        token = Token.query.get(1)
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_release,
            data={
                'token_address': token.token_address
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(2)

        url_setting = self.url_setting + token.token_address
        # 債券詳細設定
        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '公開中です。公開開始までに数分程かかることがあります。'.encode('utf-8') in response.data

        # tokenが登録されているか確認
        res_token = get_token_list(shared_contract['TokenList'], token.token_address)
        assert res_token[0] == token.token_address

    # ＜正常系11＞
    # 債券保有者一覧
    def test_normal_11(self, app, shared_contract):
        token = Token.query.get(1)
        client = self.client_with_admin_login(app)
        response = client.get(self.url_holders + token.token_address)
        assert response.status_code == 200
        assert '<title>債券保有者一覧'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '1000000'.encode('utf-8') in response.data

    # ＜正常系12＞
    # 債券保有者詳細
    def test_normal_12(self, app, shared_contract):
        token = Token.query.get(1)
        client = self.client_with_admin_login(app)
        response = client.get(self.url_holder + token.token_address + '/' + eth_account['issuer']['account_address'])
        assert response.status_code == 200
        assert '<title>債券保有者詳細'.encode('utf-8') in response.data
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '1234567'.encode('utf-8') in response.data
        assert '東京都'.encode('utf-8') in response.data
        assert '中央区'.encode('utf-8') in response.data
        assert '日本橋11-1'.encode('utf-8') in response.data
        assert '東京マンション１０１'.encode('utf-8') in response.data
        assert '三菱UFJ銀行'.encode('utf-8') in response.data
        assert '東恵比寿支店'.encode('utf-8') in response.data
        assert '普通'.encode('utf-8') in response.data
        assert 'ｶﾌﾞｼｷｶﾞｲｼﾔｹﾂｻｲﾀﾞｲｺｳ'.encode('utf-8') in response.data


    # ＜正常系13＞
    # 認定依頼
    def test_normal_13(self, app, shared_contract):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)

        # 認定画面
        response = client.get(url_signature)
        assert response.status_code == 200
        assert '<title>認定依頼'.encode('utf-8') in response.data

        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
                'signer': eth_account['agent']['account_address']
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(2)

        # 債券詳細設定
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200
        assert '<title>債券詳細設定'.encode('utf-8') in response.data
        assert '認定依頼を受け付けました。'.encode('utf-8') in response.data

        # 債券トークンのsignatureが1になっていること
        val = get_signature(token.token_address, token.abi, eth_account['agent']['account_address'])
        assert val == 1



    #############################################################################
    # エラー系
    #############################################################################
    # ＜エラー系1＞
    # 債券新規発行（必須エラー）
    def test_error_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>債券新規発行'.encode('utf-8') in response.data
        assert '商品名は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data
        assert '額面は必須です。'.encode('utf-8') in response.data
        assert '金利は必須です。'.encode('utf-8') in response.data
        assert '償還日は必須です。'.encode('utf-8') in response.data
        assert '償還金額は必須です。'.encode('utf-8') in response.data
        assert '発行目的は必須です。'.encode('utf-8') in response.data


    # ＜エラー系2＞
    # 募集（必須エラー）
    def test_error_2(self, app, shared_contract):
        token = Token.query.get(1)
        # 募集
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_sell + token.token_address,
            data={
            }
        )
        assert response.status_code == 302
        # 債券新規募集でエラーを確認
        response = client.get(self.url_sell + token.token_address)
        assert response.status_code == 200
        assert '<title>債券新規募集'.encode('utf-8') in response.data
        assert '売出価格は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3＞
    # 認定（必須エラー）
    def test_error_3(self, app, shared_contract):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)
        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
            }

        )
        assert response.status_code == 200
        assert '認定者は必須です。'.encode('utf-8') in response.data


    # ＜エラー系4＞
    # 認定（認定依頼先アドレスのフォーマットエラー）
    def test_error_4(self, app, shared_contract):
        token = Token.query.get(1)
        url_signature = self.url_signature + token.token_address
        client = self.client_with_admin_login(app)
        # 認定依頼
        response = client.post(
            url_signature,
            data={
                'token_address': token.token_address,
                'signer': '0xc94b0d702422587e361dd6cd08b55dfe1961181f1' # 1桁多い
            }
        )
        assert response.status_code == 200
        assert '有効なアドレスではありません。'.encode('utf-8') in response.data
