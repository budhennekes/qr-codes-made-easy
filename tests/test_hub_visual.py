"""Working QR hero and faithful resource-preview regressions."""
import functools
import http.server
import io
import os
from pathlib import Path
import threading
import unittest
from PIL import Image
from playwright.sync_api import sync_playwright
import zxingcpp

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=Path(os.environ.get('QR_VISUAL_QA_OUTPUT',str(ROOT.parent/'qr-optimization-qa/hub-visual-20261004/local')))
BASE=os.environ.get('QR_VISUAL_BASE_URL','')

class HubVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args): pass
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base=BASE or f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close()

    def page(self):
        ctx=self.browser.new_context()
        self.addCleanup(ctx.close)
        ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith((self.base,'https://fonts.googleapis.com/','https://fonts.gstatic.com/')) else r.abort())
        p=ctx.new_page()
        p.goto(self.base+'guides/')
        p.evaluate('document.fonts.ready')
        return p

    def test_real_qr_decodes_at_each_rendered_size(self):
        p=self.page()
        for width in (320,390,768,1280):
            with self.subTest(width=width):
                p.set_viewport_size({'width':width,'height':1000})
                self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                img=p.locator('.qr-demo img')
                png=img.screenshot()
                result=zxingcpp.read_barcode(Image.open(io.BytesIO(png)))
                self.assertIsNotNone(result)
                self.assertEqual(result.text,'https://qrcodemadeeasy.com/#tool')
                self.assertEqual(p.locator('.qr-demo').get_attribute('href'),'/#tool')
                p.evaluate('window.scrollTo(0,0)')
                p.screenshot(path=str(OUTPUT/f'hub-{width}.png'),full_page=True)
                p.screenshot(path=str(OUTPUT/f'hero-{width}.png'))

    def test_keyboard_demo_and_resource_links(self):
        p=self.page()
        p.locator('.qr-demo').focus()
        self.assertEqual(p.locator('.qr-demo').evaluate('(e)=>getComputedStyle(e).outlineStyle'),'solid')
        p.keyboard.press('Enter')
        p.wait_for_url(self.base+'#tool')
        self.assertTrue(p.locator('#url-input').is_visible())
        p.goto(self.base+'guides/')
        p.locator('.resource-item a[href="/resources/guest-wifi-sign.html"]').click()
        self.assertTrue(p.url.endswith('/resources/guest-wifi-sign.html'))
        p.goto(self.base+'guides/')
        with p.expect_download() as event:
            p.locator('.resource-item a[download]').click()
        dest=OUTPUT/'checklist.pdf'
        event.value.save_as(dest)
        self.assertEqual(dest.read_bytes(),(ROOT/'resources/qr-print-checklist.pdf').read_bytes())

    def test_preview_images_and_reduced_motion(self):
        p=self.page()
        for img in p.locator('.resource-preview img').all():
            img.scroll_into_view_if_needed()
            img.evaluate('(e)=>e.decode()')
            self.assertTrue(img.evaluate('(e)=>e.naturalWidth>0 && e.naturalHeight>0'))
            self.assertTrue(img.evaluate('(e)=>e.naturalWidth===Number(e.getAttribute("width")) && e.naturalHeight===Number(e.getAttribute("height"))'))
        p.emulate_media(reduced_motion='reduce')
        p.locator('.qr-demo').hover()
        self.assertEqual(p.locator('.demo-action svg').evaluate('(e)=>getComputedStyle(e).transform'),'none')
        # White on the existing blue must pass normal-text AA.
        def linear(c):
            c=c/255
            return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
        luminance=sum(a*linear(b) for a,b in zip((.2126,.7152,.0722),(37,99,235)))
        self.assertGreaterEqual(1.05/(luminance+.05),4.5)

if __name__=='__main__': unittest.main(verbosity=2)
