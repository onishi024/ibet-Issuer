# -*- coding:utf-8 -*-
import pytest
import os
import time

from .conftest import TestBase
from .account_config import eth_account
from config import Config
from .contract_modules import register_only_whitelist
from ..models import Token

from logging import getLogger
logger = getLogger('api')

class TestWhiteList(TestBase):
    issuer_encrypted_info = 'hekR0bz6qfsnaIYLZ7emUNaynqHFQsrwehcMq8r0tw2SRSM2vhb4B9HZWNaB0pOF7Obtp6qQM59ADfpwoGw3KewOw/4ZmPG7ajFaDYP1CHwz+LaxcQciJDi07ROZYDKwxukbGVcRxWwRJdjt9fOjLJzcgEyTG44LqxAjaGANVQnf3ZF3I6iZ84FrDKTGQ/86Qzv/Mj53nGkU053J6p8/RWU3n1vOtwOOMSwqc2gZlCEMqjjKxkkFUxbVZAFXNMiLgOAsnvBsq49Tr0J4ei0M+j4uWnbxsB2mMdKJTY69jiCOgiTa/of//W9H/jl0PzTINXb59xLTDuER8Ni7UYCU2MIcWzsQY6+2kzpkSglqG3JXB/iQjg+TZUXgeRIVZvo1uecdKRegJbcNt/xn1HH1FzO6kxmcHP/GML5Hh0AXwswkzdDhJZExWYVJ6+W8Uc/OlO1Y1SzScX7I7f7WcsDgPrxuV+oVWl/e+bBroi6UAJAappq17n5ZxGB9vgDb4tQLXCV/hyyo61O4hg8Ca7jH2imxN4612e/Z5ZrZPQf9rnMJXLPF57r1lECC2xvfjTdhEmBblO1ynY/hlgW7mscgrZDMfr/shsdrQyqH1yExAmN9puR2X96Ejqn+lRBbhi9kqxAAnP1G4S3S9EDgMc1yiCmq4mLVZO/SyCbKzytXOmScMHWyPmcjfjt+uuxkWM6NifUkeWcc3NjXLDjwj1ipuegJJnVoAje950w3HEWBzxX2W16EHlzEdovXGObtV8WP/p+Q/WesPyE9s1gh/ND19APBQx7+TR7LepCTOA1cmFl/JTFFk37dGRka34CTDjqF+kan0sk/JPGytbmLMWEbZiZkDhcZ8kTI9EpTYeS4se5B3X4Nd/Fi6k/kGSK0FtYakwmc0q30eWnDyE049MmdZQV/QdARCrNWipv1WRbL5oNlP9pbR8Mz3pMcISofLdyrWtdJCgj1sNj/CXFai+4F2ce5wQZb95kCyrN0AT2zj8JAuZImeTDDUQpnn++iMGWkWKYPnRaw5Jel9OcYKbgsqvSyzTzSgfWvUMZxD0Fz6SLOeGKvWDlSDVi/jFOZZxWy4EYElBklc47eehlMQHGQT/6PZVnZbuf43j1EF8+s4VMLf7nnb1JG6tQ2gTYx/UG+arK25f5ZXnzaOQNX5X2Hu/Bv/s1PmaXa1QcEIuByumNFra7iNnhT/6DTgNAVPlbTUbTLrc+8kVft2VDIe1FUG4UNjpDGjP/j/Ovjy3prMrWdBAXcLvRuVk9NMiMa4qQIuVE+Dd4hw+47At8LIfu6pCwiX5cRPCCVEzZ5I8il41qbvdIjQ2ewANB0j1Ve3hrbUQcZcF/MMKGPHwRDaAprQ9oZZVX+pVrcZmD/EQr9A0NvRhvcQb1JdOIaOyWnMfj0r3Ki0eIp2seLtqQ9Mpxje+plCqHfy5FXunLMi3U5FzTLkPmt5ANiNtE5E9X6hqzBgSW4dR+plJbrsE0JvmNFxefiN2tTj9QOuOKy2QXdc3oR79Mi4KKKdti2sS6wopX8kkMSzK+LZ8Fr98FeKX/uLXj1T4o7xb65HG3i45kDhv5cGilkNyI8euOsEsMlfQbboITQpcRhspzunJXfHx9sEpiVjFL+vMR/vcNblJ3zZUtiOoqeQEynH7paCa2vxURLeJ3PsmfowIO8ZebX+ZWM8ElpNIG0l43SxoGFUP/tI78='
    trader_encrypted_info = 'Upu+PwVJUYV30KMTrrDwEHTT/u6Px+5VdRWx+FZdKuJ/36TvIBJEsyf4bv/dgZwcOoBztWQnQ71Cf55fBkopqjpHm7YJpeRnEdqRVwOc44PynVdcZeQvWizU867ub5QUh/coG5ftCB5ln3UcunEMbxmOLpjnTmNSRdIz0iWdYU/gxFuHNVxexTgSpvhUp4R7QrY/mBp5g6reYILCjy9wabJ8i7iSEOjP5szmtmCDIqhBnidtmoVxfgDGUDYpL3HU8HmfDIwCc+YuUORS3LSBVWshEK9EO89flghnI/wozsh7vntcGXKfNkVkfwZx9C0q878+Ep+p6pFpU4HMGbjTEtFsozEjZT22wAMfMDZOoBOsrURM0PGom6bJ/zfrAKr9oAWgjvBkaYLknxagwOosVLQH/QF31mlQyFScXJEISsi023S7l/nDJ3DVPS8ejghWgvAUcfwOSA7Vt9fS2KLUTUbd+RTd4FL9uks+A3rm0yL2Jc/Px4fpbnENBrenqSyBl1sYw7JLvvfut/hz6qUiOswoy2G0tZszKGo9nZiOMkmAr5sv2xh4M380uG8KOf3PaZXm6elFPqCOilHAZpQfydA1y1M7QgVIa+WkO53HevVUn9iqk/u6q5x3xA3HgneiZFGXWCzJwnV+GMkR0ILGbugkP5bl/nlji/grev40jEdWlVy2tazHwh+2fH6QBTWfiTVvrPTcprWy0GAjqAwPyCuCkMcjr9invpkuwaI7BugbAyWA8o1ANv35hinVnNtpgbesJjHxJWlbE7x4Ph+Big2W5o+DdZpnIYFtBOi6YdB50lvemFcktFUewCRzzB5cO3wgkvpxkgPGpy3mq0GSB7gJqmJ28RVjjOyNCmbVsl0V3Sgq3YhpfIyeoFZ8YQCz+m8QXXEDUeLdkms2yKmaIYZqinXgRNxaQdwdgxbYYyamf9Ena3E+KeLuHSOq3xtupgHopv2Y6c1/hBznKy6gVJVbfEMYRWYqUM7KYLZahcaLvFP8YuD7nTx7r6tKH6OaQi12FO+Pnk98kvG66VWM+i/AlWvNSI+3Cx50sDW5BF7Rl9DNB59AfX7Ur7Pdn7lfDTy6fDLqGs+LtmYUOtt8YlL6mAmH1x7pV5nF+01CnaShAC430cQyBB2vngs/p4FS654z0dIkEZ6YLSCIBIJpNYJY2oGOixNTrG+4lECKyQ0HY4AmtXnH5iqgS9/NCcLHHBWiqIXQgCQ5sCUVTIe0cHu6fWLrDtAlBncrX/6gEix0N/O6OQHfVx3veHRYGMJ1ZIM25gqI/ccgz9IyKtG//8zGqruvt6y8e6xJ7yh3OnSHPbNmLd8hcY9Ti2gQnMbKe2hDFQJehLRawNG8Yujd0H3ROnypEaCF2m7hKy23w3vmeVnPMM6xYshCsjXInjjiXn8xLof5NUA9Ea8d2U/3DaGPm4Xgt9VV0hilTKAKRQsSSG9YBrg6iGI6IKnka3tD7iKOvsBahZstNw4xEn7NifYPatCJjHDKaSqeqrdS9U9T0ClnG4iD5U8ufIEtvHKewDMOpVD6KW/lszilrziA6hSUyVPBx/p/VHhhAXXJ8ISvk+TLrpRvUukE4CtwqE/rdryeBvYM7XKqnqV72zOlirnlx2iiaQWm6XfSGdfjaUt2J5VSbwHv5lv534CCWrqBC7V/X9KISx1UV0regXvOtOen2UV2xshEv2ljrWjGPFY='
    url_tokenlist = '/token/tokenlist' # 発行済債券一覧
    url_issue = '/token/issue' # 債券新規発行
    url_setting = '/token/setting/' # 設定画面

    # ＜正常系1_1＞
    # 発行済債券一覧の参照(0件)
    def test_normal_1_1(self, app):      
        client = self.client_with_admin_login(app)
        response = client.get(self.url_tokenlist)
        assert response.status_code == 200
        assert '<title>発行済債券一覧'.encode('utf-8') in response.data
        assert 'データが存在しません'.encode('utf-8') in response.data

    # ＜正常系1_2＞
    # 新規発行　→　発行済債券一覧の参照(1件) →　詳細画面
    def test_normal_1_2(self, app, db):
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

        # 5秒待機
        time.sleep(5)

        # 一覧
        response = client.get(self.url_tokenlist)
        assert response.status_code == 200
        assert '<title>発行済債券一覧'.encode('utf-8') in response.data
        assert 'テスト債券'.encode('utf-8') in response.data
        assert 'BOND'.encode('utf-8') in response.data

        # 設定画面
        token = Token.query.filter(Token.id==1).first()
        response = client.get(self.url_setting + token.token_address)
        assert response.status_code == 200



