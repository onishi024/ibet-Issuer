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

class TestCoupon(TestBase):
    issuer_encrypted_info = 'hekR0bz6qfsnaIYLZ7emUNaynqHFQsrwehcMq8r0tw2SRSM2vhb4B9HZWNaB0pOF7Obtp6qQM59ADfpwoGw3KewOw/4ZmPG7ajFaDYP1CHwz+LaxcQciJDi07ROZYDKwxukbGVcRxWwRJdjt9fOjLJzcgEyTG44LqxAjaGANVQnf3ZF3I6iZ84FrDKTGQ/86Qzv/Mj53nGkU053J6p8/RWU3n1vOtwOOMSwqc2gZlCEMqjjKxkkFUxbVZAFXNMiLgOAsnvBsq49Tr0J4ei0M+j4uWnbxsB2mMdKJTY69jiCOgiTa/of//W9H/jl0PzTINXb59xLTDuER8Ni7UYCU2MIcWzsQY6+2kzpkSglqG3JXB/iQjg+TZUXgeRIVZvo1uecdKRegJbcNt/xn1HH1FzO6kxmcHP/GML5Hh0AXwswkzdDhJZExWYVJ6+W8Uc/OlO1Y1SzScX7I7f7WcsDgPrxuV+oVWl/e+bBroi6UAJAappq17n5ZxGB9vgDb4tQLXCV/hyyo61O4hg8Ca7jH2imxN4612e/Z5ZrZPQf9rnMJXLPF57r1lECC2xvfjTdhEmBblO1ynY/hlgW7mscgrZDMfr/shsdrQyqH1yExAmN9puR2X96Ejqn+lRBbhi9kqxAAnP1G4S3S9EDgMc1yiCmq4mLVZO/SyCbKzytXOmScMHWyPmcjfjt+uuxkWM6NifUkeWcc3NjXLDjwj1ipuegJJnVoAje950w3HEWBzxX2W16EHlzEdovXGObtV8WP/p+Q/WesPyE9s1gh/ND19APBQx7+TR7LepCTOA1cmFl/JTFFk37dGRka34CTDjqF+kan0sk/JPGytbmLMWEbZiZkDhcZ8kTI9EpTYeS4se5B3X4Nd/Fi6k/kGSK0FtYakwmc0q30eWnDyE049MmdZQV/QdARCrNWipv1WRbL5oNlP9pbR8Mz3pMcISofLdyrWtdJCgj1sNj/CXFai+4F2ce5wQZb95kCyrN0AT2zj8JAuZImeTDDUQpnn++iMGWkWKYPnRaw5Jel9OcYKbgsqvSyzTzSgfWvUMZxD0Fz6SLOeGKvWDlSDVi/jFOZZxWy4EYElBklc47eehlMQHGQT/6PZVnZbuf43j1EF8+s4VMLf7nnb1JG6tQ2gTYx/UG+arK25f5ZXnzaOQNX5X2Hu/Bv/s1PmaXa1QcEIuByumNFra7iNnhT/6DTgNAVPlbTUbTLrc+8kVft2VDIe1FUG4UNjpDGjP/j/Ovjy3prMrWdBAXcLvRuVk9NMiMa4qQIuVE+Dd4hw+47At8LIfu6pCwiX5cRPCCVEzZ5I8il41qbvdIjQ2ewANB0j1Ve3hrbUQcZcF/MMKGPHwRDaAprQ9oZZVX+pVrcZmD/EQr9A0NvRhvcQb1JdOIaOyWnMfj0r3Ki0eIp2seLtqQ9Mpxje+plCqHfy5FXunLMi3U5FzTLkPmt5ANiNtE5E9X6hqzBgSW4dR+plJbrsE0JvmNFxefiN2tTj9QOuOKy2QXdc3oR79Mi4KKKdti2sS6wopX8kkMSzK+LZ8Fr98FeKX/uLXj1T4o7xb65HG3i45kDhv5cGilkNyI8euOsEsMlfQbboITQpcRhspzunJXfHx9sEpiVjFL+vMR/vcNblJ3zZUtiOoqeQEynH7paCa2vxURLeJ3PsmfowIO8ZebX+ZWM8ElpNIG0l43SxoGFUP/tI78='
    trader_encrypted_info = 'Upu+PwVJUYV30KMTrrDwEHTT/u6Px+5VdRWx+FZdKuJ/36TvIBJEsyf4bv/dgZwcOoBztWQnQ71Cf55fBkopqjpHm7YJpeRnEdqRVwOc44PynVdcZeQvWizU867ub5QUh/coG5ftCB5ln3UcunEMbxmOLpjnTmNSRdIz0iWdYU/gxFuHNVxexTgSpvhUp4R7QrY/mBp5g6reYILCjy9wabJ8i7iSEOjP5szmtmCDIqhBnidtmoVxfgDGUDYpL3HU8HmfDIwCc+YuUORS3LSBVWshEK9EO89flghnI/wozsh7vntcGXKfNkVkfwZx9C0q878+Ep+p6pFpU4HMGbjTEtFsozEjZT22wAMfMDZOoBOsrURM0PGom6bJ/zfrAKr9oAWgjvBkaYLknxagwOosVLQH/QF31mlQyFScXJEISsi023S7l/nDJ3DVPS8ejghWgvAUcfwOSA7Vt9fS2KLUTUbd+RTd4FL9uks+A3rm0yL2Jc/Px4fpbnENBrenqSyBl1sYw7JLvvfut/hz6qUiOswoy2G0tZszKGo9nZiOMkmAr5sv2xh4M380uG8KOf3PaZXm6elFPqCOilHAZpQfydA1y1M7QgVIa+WkO53HevVUn9iqk/u6q5x3xA3HgneiZFGXWCzJwnV+GMkR0ILGbugkP5bl/nlji/grev40jEdWlVy2tazHwh+2fH6QBTWfiTVvrPTcprWy0GAjqAwPyCuCkMcjr9invpkuwaI7BugbAyWA8o1ANv35hinVnNtpgbesJjHxJWlbE7x4Ph+Big2W5o+DdZpnIYFtBOi6YdB50lvemFcktFUewCRzzB5cO3wgkvpxkgPGpy3mq0GSB7gJqmJ28RVjjOyNCmbVsl0V3Sgq3YhpfIyeoFZ8YQCz+m8QXXEDUeLdkms2yKmaIYZqinXgRNxaQdwdgxbYYyamf9Ena3E+KeLuHSOq3xtupgHopv2Y6c1/hBznKy6gVJVbfEMYRWYqUM7KYLZahcaLvFP8YuD7nTx7r6tKH6OaQi12FO+Pnk98kvG66VWM+i/AlWvNSI+3Cx50sDW5BF7Rl9DNB59AfX7Ur7Pdn7lfDTy6fDLqGs+LtmYUOtt8YlL6mAmH1x7pV5nF+01CnaShAC430cQyBB2vngs/p4FS654z0dIkEZ6YLSCIBIJpNYJY2oGOixNTrG+4lECKyQ0HY4AmtXnH5iqgS9/NCcLHHBWiqIXQgCQ5sCUVTIe0cHu6fWLrDtAlBncrX/6gEix0N/O6OQHfVx3veHRYGMJ1ZIM25gqI/ccgz9IyKtG//8zGqruvt6y8e6xJ7yh3OnSHPbNmLd8hcY9Ti2gQnMbKe2hDFQJehLRawNG8Yujd0H3ROnypEaCF2m7hKy23w3vmeVnPMM6xYshCsjXInjjiXn8xLof5NUA9Ea8d2U/3DaGPm4Xgt9VV0hilTKAKRQsSSG9YBrg6iGI6IKnka3tD7iKOvsBahZstNw4xEn7NifYPatCJjHDKaSqeqrdS9U9T0ClnG4iD5U8ufIEtvHKewDMOpVD6KW/lszilrziA6hSUyVPBx/p/VHhhAXXJ8ISvk+TLrpRvUukE4CtwqE/rdryeBvYM7XKqnqV72zOlirnlx2iiaQWm6XfSGdfjaUt2J5VSbwHv5lv534CCWrqBC7V/X9KISx1UV0regXvOtOen2UV2xshEv2ljrWjGPFY='
    url_list = 'coupon/list' # クーポン一覧
    url_issue = 'coupon/issue' # 発行
    url_setting = 'coupon/setting/' # 設定画面
    url_valid = 'coupon/valid' # 有効化
    url_invalid = 'coupon/invalid' # 無効化
    url_add_supply = 'coupon/add_supply/' # 追加発効
    url_transfer = 'coupon/transfer' # 割当
    url_holders = 'coupon/holders/' # 保有者一覧
    url_holder = 'coupon/holder/' # 保有者詳細

    # ＜正常系1＞
    # 一覧の参照(0件)
    def test_normal_1(self, app, shared_contract):
        # Config設定は1_1で全て実施
        Config.ETH_ACCOUNT = eth_account['issuer']['account_address']
        Config.ETH_ACCOUNT_PASSWORD = eth_account['issuer']['password']
        Config.AGENT_ADDRESS = eth_account['agent']['account_address']
        Config.IBET_SB_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetStraightBondExchange']['address']
        Config.WHITE_LIST_CONTRACT_ADDRESS = shared_contract['WhiteList']['address']
        Config.TOKEN_LIST_CONTRACT_ADDRESS = shared_contract['TokenList']['address']
        Config.PERSONAL_INFO_CONTRACT_ADDRESS = shared_contract['PersonalInfo']['address']
        Config.IBET_COUPON_EXCHANGE_CONTRACT_ADDRESS = shared_contract['IbetCouponExchange']['address']

        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系2＞
    # 新規発行　→　DB登録処理 →　詳細画面
    def test_normal_2(self, app, db, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
                'name': 'テストクーポン',
                'symbol': 'COUPON',
                'totalSupply': 2000000,
                'expirationDate': '20191231',
                'transferable': True,
                'details': 'details詳細',
                'memo': 'memoメモ',
                'image_small': 'https://test.com/image_small.jpg',
                'image_medium': 'https://test.com/image_medium.jpg',
                'image_large': 'https://test.com/image_large.jpg'
            }
        )
        assert response.status_code == 302

        # 5秒待機
        time.sleep(10)

        # DB登録処理
        processorIssueEvent(db)

        # 設定画面
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        response = client.get(self.url_setting + tokens[0].token_address)
    
        assert response.status_code == 200
        assert '<title>クーポン編集'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '<option selected value="True">あり</option>'.encode('utf-8') in response.data
        assert 'details詳細'.encode('utf-8') in response.data
        assert 'memoメモ'.encode('utf-8') in response.data
        assert 'https://test.com/image_small.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_medium.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_large.jpg'.encode('utf-8') in response.data

    # ＜正常系3＞
    # 一覧の参照(1件)
    def test_normal_3(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '有効'.encode('utf-8') in response.data

    # ＜正常系4＞
    # クーポン編集　→　画面で確認
    def test_normal_4(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_setting = self.url_setting + tokens[0].token_address
        client = self.client_with_admin_login(app)
        # 募集設定
        response = client.post(
            url_setting,
            data={
                'details': 'details詳細2',
                'memo': 'memoメモ2',
                'image_small': 'https://test.com/image_small2.jpg',
                'image_medium': 'https://test.com/image_medium2.jpg',
                'image_large': 'https://test.com/image_large2.jpg',
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(10)

        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン編集'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '<option selected value="True">あり</option>'.encode('utf-8') in response.data
        assert 'details詳細2'.encode('utf-8') in response.data
        assert 'memoメモ2'.encode('utf-8') in response.data
        assert 'https://test.com/image_small2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_medium2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_large2.jpg'.encode('utf-8') in response.data

    # ＜正常系5＞
    # 有効化/無効化
    def test_normal_5(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)

        # 無効化
        response = client.post(
            self.url_invalid,
            data={
                'token_address': tokens[0].token_address
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(2)

        # 一覧で確認
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '無効'.encode('utf-8') in response.data

        # 無効化
        response = client.post(
            self.url_valid,
            data={
                'token_address': tokens[0].token_address
            }
        )
        assert response.status_code == 302

        # 待機
        time.sleep(2)

        # 一覧で確認
        response = client.get(self.url_list)
        assert response.status_code == 200
        assert '<title>クーポン一覧'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '有効'.encode('utf-8') in response.data

    # ＜正常系6＞
    # 追加発効
    def test_normal_6(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_add_supply = self.url_add_supply + tokens[0].token_address
        url_setting = self.url_setting + tokens[0].token_address
        client = self.client_with_admin_login(app)

        # 一覧で確認
        response = client.get(url_add_supply)
        assert response.status_code == 200
        assert '<title>クーポン追加発行'.encode('utf-8') in response.data
        assert tokens[0].token_address.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data

        # 追加
        response = client.post(
            url_add_supply,
            data={
                'addSupply': 100
            }
        )
        assert response.status_code == 302

        time.sleep(2)

        response = client.get(url_setting)
        assert response.status_code == 200
        assert '<title>クーポン編集'.encode('utf-8') in response.data
        assert 'テストクーポン'.encode('utf-8') in response.data
        assert 'COUPON'.encode('utf-8') in response.data
        assert '2000100'.encode('utf-8') in response.data
        assert '20191231'.encode('utf-8') in response.data
        assert '<option selected value="True">あり</option>'.encode('utf-8') in response.data
        assert 'details詳細2'.encode('utf-8') in response.data
        assert 'memoメモ2'.encode('utf-8') in response.data
        assert 'https://test.com/image_small2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_medium2.jpg'.encode('utf-8') in response.data
        assert 'https://test.com/image_large2.jpg'.encode('utf-8') in response.data

    # ＜正常系7＞
    # クーポン割当　→　保有者一覧で確認
    def test_normal_7(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)
        response = client.post(
            self.url_transfer,
            data={
                'tokenAddress': tokens[0].token_address,
                'sendAddress': eth_account['trader']['account_address'],
                'sendAmount': 100,
            }
        )
        assert response.status_code == 200
        
        time.sleep(2)

        response = client.get(self.url_holders + tokens[0].token_address)
        assert response.status_code == 200
        assert '<title>クーポン保有者一覧'.encode('utf-8') in response.data
        # issuer
        assert eth_account['issuer']['account_address'].encode('utf-8') in response.data
        assert '株式会社１'.encode('utf-8') in response.data
        assert '2000000'.encode('utf-8') in response.data # issuerの保有数量
        # trader
        assert eth_account['trader']['account_address'].encode('utf-8') in response.data
        assert 'ﾀﾝﾀｲﾃｽﾄ'.encode('utf-8') in response.data
        assert '100'.encode('utf-8') in response.data # traderの保有数量

    # ＜正常系8＞
    # 保有者詳細
    def test_normal_8(self, app, shared_contract):
        # personalinfo登録
        register_personalinfo(eth_account['issuer'], shared_contract['PersonalInfo'], self.issuer_encrypted_info)
        # 参照
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        client = self.client_with_admin_login(app)
        response = client.get(self.url_holder + tokens[0].token_address + '/' + eth_account['issuer']['account_address'])
        assert response.status_code == 200
        assert '<title>保有者詳細'.encode('utf-8') in response.data
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

    #############################################################################
    # エラー系
    #############################################################################
    # ＜エラー系1＞
    # 新規発行（必須エラー）
    def test_error_1(self, app, shared_contract):
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            self.url_issue,
            data={
            }
        )
        assert response.status_code == 200
        assert '<title>クーポン発行'.encode('utf-8') in response.data
        assert 'クーポン名は必須です。'.encode('utf-8') in response.data
        assert '略称は必須です。'.encode('utf-8') in response.data
        assert '総発行量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系2＞
    # 追加発行（必須エラー）
    def test_error_2(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_add_supply = self.url_add_supply + tokens[0].token_address
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            url_add_supply,
            data={}
        )
        assert response.status_code == 200
        assert '<title>クーポン追加発行'.encode('utf-8') in response.data
        assert '追加発行する数量は必須です。'.encode('utf-8') in response.data

    # ＜エラー系3＞
    # （必須エラー）
    def test_error_3(self, app, shared_contract):
        tokens = Token.query.filter_by(template_id=Config.TEMPLATE_ID_COUPON).all()
        url_add_supply = self.url_add_supply + tokens[0].token_address
        client = self.client_with_admin_login(app)
        # 新規発行
        response = client.post(
            url_add_supply,
            data={}
        )
        assert response.status_code == 200
        assert '<title>クーポン割当'.encode('utf-8') in response.data
        assert '債券アドレスは必須です。'.encode('utf-8') in response.data
        assert '割当先アドレスは必須です。'.encode('utf-8') in response.data
        assert '割当数量は必須です。'.encode('utf-8') in response.data
