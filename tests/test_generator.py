"""Local-only regression tests. See tests/README.md for isolated dependencies."""
import base64
import functools
import http.server
import io
import json
import os
from pathlib import Path
import threading
import unittest
from PIL import Image
import zxingcpp
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('QR_QA_OUTPUT', '/tmp/qr-code-qa'))

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900}, accept_downloads=True)
        # No test input goes to analytics, fonts, or any other third party.
        self.context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(self.url) else route.abort())
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.goto(self.url)
        self.page.wait_for_selector('#qr-preview canvas')

    def tearDown(self):
        self.context.close()
        self.assertEqual([], self.errors)

    def ready(self):
        self.page.wait_for_function("document.querySelector('#destination-status').classList.contains('ready')")
        self.page.wait_for_timeout(150)

    def decoded_preview(self):
        uri = self.page.locator('#qr-preview canvas').evaluate('(c)=>c.toDataURL()')
        image = Image.open(io.BytesIO(base64.b64decode(uri.split(',')[1])))
        decoded = zxingcpp.read_barcode(image)
        self.assertIsNotNone(decoded, 'Preview must decode')
        return decoded.text

    def test_all_six_types_decode_and_download(self):
        fixtures = [
            ('link', {'url-input':'example.com/menu?utm_source=qr'}, 'https://example.com/menu?utm_source=qr'),
            ('whatsapp', {'wa-number':'2025550123','wa-message':'Hello there'}, 'https://wa.me/12025550123?text=Hello%20there'),
            ('telegram', {'tg-input':'@example_shop'}, 'https://t.me/example_shop'),
            ('imessage', {'im-number':'2025550123','im-message':'Hello'}, 'sms:+12025550123?&body=Hello'),
            ('wifi', {'wifi-ssid':' Guest;Net ','wifi-pass':'test:pass'}, 'WIFI:T:WPA;S: Guest\\;Net ;P:test\\:pass;;'),
            ('vcard', {'vc-name':'Test Person','vc-phone':'2025550123'}, 'BEGIN:VCARD\nVERSION:3.0\nN:Person;Test;;;\nFN:Test Person\nTEL;TYPE=CELL:2025550123\nEND:VCARD')
        ]
        for kind, fields, expected in fixtures:
            with self.subTest(kind=kind):
                self.page.locator('#tab-'+kind).click()
                for field, value in fields.items():
                    self.page.locator('#'+field).fill(value)
                self.ready()
                self.assertEqual(expected, self.decoded_preview())
                with self.page.expect_download() as event:
                    self.page.locator('#dl-png').click()
                path = OUTPUT / f'{kind}.png'
                event.value.save_as(path)
                self.assertEqual(expected, zxingcpp.read_barcode(Image.open(path)).text)
                with self.page.expect_download() as event:
                    self.page.locator('#dl-svg').click()
                path = OUTPUT / f'{kind}.svg'
                event.value.save_as(path)
                text = path.read_text()
                self.assertIn('<svg', text)
                self.assertNotIn('<script', text)
                # Render and decode the actual SVG export, not just its markup.
                decoded_uri = self.page.evaluate('''async svg => {
                    const image = new Image();
                    image.src = URL.createObjectURL(new Blob([svg], {type:'image/svg+xml'}));
                    await image.decode();
                    const c=document.createElement('canvas'); c.width=1000; c.height=1000;
                    c.getContext('2d').drawImage(image,0,0); URL.revokeObjectURL(image.src);
                    return c.toDataURL();
                }''', text)
                decoded = zxingcpp.read_barcode(Image.open(io.BytesIO(base64.b64decode(decoded_uri.split(',')[1]))))
                self.assertIsNotNone(decoded)
                self.assertEqual(expected, decoded.text)

    def test_overflow_blocks_stale_preview_and_recovers(self):
        self.page.locator('#url-input').fill('https://example.com/')
        self.ready()
        self.page.locator('#url-input').fill('https://example.com/'+'a'*6000)
        self.page.wait_for_function("document.querySelector('#destination-status').classList.contains('error')")
        self.assertIn('Too much data', self.page.locator('#destination-status').inner_text())
        self.assertTrue(self.page.locator('#qr-preview').is_hidden())
        for button in ['dl-png','dl-svg','share-btn','embed-btn']:
            self.assertTrue(self.page.locator('#'+button).is_disabled())
        self.page.locator('#url-input').fill('https://example.com/recovered')
        self.ready()
        self.assertEqual('https://example.com/recovered', self.decoded_preview())

    def test_fast_typing_coalesces_work(self):
        self.page.evaluate('''() => {window.updates=0;const original=QRCodeStyling.prototype.update;
            QRCodeStyling.prototype.update=function(...a){window.updates++;return original.apply(this,a)};}''')
        self.page.locator('#url-input').press_sequentially('https://example.com/menu?campaign=summer', delay=10)
        self.ready()
        self.assertLessEqual(self.page.evaluate('window.updates'), 2)
        self.assertEqual('https://example.com/menu?campaign=summer', self.decoded_preview())

    def test_logo_remove_and_all_presets(self):
        self.page.locator('#url-input').fill('https://example.com/menu')
        self.ready()
        before = self.page.locator('#qr-preview canvas').evaluate('(c)=>c.toDataURL()')
        for preset in ['rounded','dots','print','classic']:
            self.page.locator('[data-preset="'+preset+'"]').click()
            self.ready()
            self.assertEqual('https://example.com/menu', self.decoded_preview())
        logo = io.BytesIO()
        Image.new('RGB', (80,80), '#2563eb').save(logo, 'PNG')
        self.page.locator('#logo-input').set_input_files({'name':'test-logo.png','mimeType':'image/png','buffer':logo.getvalue()})
        self.page.wait_for_function("document.querySelector('#logo-clear').style.display==='inline'")
        self.ready()
        self.assertEqual('https://example.com/menu', self.decoded_preview())
        self.page.locator('#logo-clear').click()
        self.ready()
        self.assertEqual(before, self.page.locator('#qr-preview canvas').evaluate('(c)=>c.toDataURL()'))

    def test_empty_invalid_and_keyboard_tabs(self):
        self.assertTrue(self.page.locator('#dl-png').is_disabled())
        self.page.locator('#url-input').fill('https://')
        self.page.wait_for_timeout(300)
        self.assertTrue(self.page.locator('#dl-png').is_disabled())
        self.page.locator('#tab-link').focus()
        self.page.keyboard.press('End')
        self.assertEqual('true', self.page.locator('#tab-vcard').get_attribute('aria-selected'))
        self.assertTrue(self.page.locator('#pane-link').is_hidden())

    def test_quiet_zone_at_least_four_modules(self):
        self.page.locator('#url-input').fill('https://a.co')
        self.ready()
        with self.page.expect_download() as event:
            self.page.locator('#dl-png').click()
        image = Image.open(event.value.path()).convert('RGB')
        # Top-left finder pattern spans seven modules: compare leading margin to its width.
        dark = lambda px: sum(px) < 300
        first_y = next(y for y in range(image.height) if any(dark(image.getpixel((x,y))) for x in range(image.width)))
        row = [dark(image.getpixel((x,first_y))) for x in range(image.width)]
        first_x = row.index(True)
        end = next(x for x in range(first_x,image.width) if not row[x])
        module = (end-first_x)/7
        self.assertGreaterEqual(first_x/module, 4)
        self.assertGreaterEqual(first_y/module, 4)

    def test_mobile_layout_and_reduced_motion(self):
        self.page.emulate_media(reduced_motion='reduce')
        for width in [320,390,768,1280]:
            self.page.set_viewport_size({'width':width,'height':900})
            self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
        self.page.set_viewport_size({'width':390,'height':844})
        word = self.page.locator('#rotator-word').inner_text()
        self.page.wait_for_timeout(2900)
        self.assertEqual(word,self.page.locator('#rotator-word').inner_text())
        self.page.screenshot(path=str(OUTPUT/'mobile-top.png'))
        self.page.locator('.tool').screenshot(path=str(OUTPUT/'mobile-generator.png'))
        self.page.set_viewport_size({'width':1280,'height':900})
        self.page.screenshot(path=str(OUTPUT/'desktop-top.png'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
