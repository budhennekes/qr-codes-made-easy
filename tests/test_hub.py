"""Local hub/resource regressions. Synthetic inputs; no personal browser."""
import functools
import http.server
import io
import json
import os
from pathlib import Path
import threading
import unittest
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import sync_playwright
import pymupdf as fitz
import zxingcpp

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('QR_HUB_QA_OUTPUT', str(ROOT.parent / 'qr-optimization-qa/hub-20261004/tests')))
ROUTES = ['guides/', 'guides/qr-code-for-wifi/', 'guides/how-big-should-a-qr-code-be-for-print/', 'guides/why-wont-my-qr-code-scan/', 'for/restaurants/', 'for/small-business/', 'resources/guest-wifi-sign.html', 'resources/qr-print-checklist.html']

def doc(path):
    return BeautifulSoup(path.read_text(), 'html.parser')

class HubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def context(self):
        ctx = self.browser.new_context(viewport={'width': 390, 'height': 844})
        ctx.route('**/*', lambda r: r.continue_() if r.request.url.startswith(self.base) else r.abort())
        self.addCleanup(ctx.close)
        return ctx

    def test_hub_keeps_all_guides_in_four_task_groups(self):
        hub = doc(ROOT / 'guides/index.html')
        groups = hub.select('section.topic-group')
        self.assertEqual([x['id'] for x in groups], ['reviews', 'guests', 'print', 'promotion'])
        targets = set()
        for a in hub.select('section.topic-group a[href]'):
            p = urlparse(urljoin(self.base + 'guides/', a['href'])).path
            if p.startswith('/guides/') and p != '/guides/':
                targets.add(p)
        expected = {'/guides/' + p.parent.name + '/' for p in (ROOT / 'guides').glob('*/index.html')}
        self.assertEqual(targets, expected)
        self.assertEqual(len(expected), 20)
        for target in ['/resources/guest-wifi-sign.html', '/resources/qr-print-checklist.pdf']:
            self.assertIsNotNone(hub.find('a', href=target))
        self.assertIn('visits', hub.get_text())

    def test_changed_pages_links_schema_and_faq_parity(self):
        for route in ROUTES:
            path = ROOT / route
            if path.is_dir():
                path /= 'index.html'
            with self.subTest(route=route):
                page = doc(path)
                self.assertEqual(len(page.select('h1')), 1)
                for a in page.select('a[href],img[src]'):
                    value = a.get('href', a.get('src'))
                    u = urlparse(urljoin('https://qrcodemadeeasy.com/' + route, value))
                    if u.netloc != 'qrcodemadeeasy.com':
                        continue
                    target = ROOT / unquote(u.path).lstrip('/')
                    if target.is_dir():
                        target /= 'index.html'
                    self.assertTrue(target.is_file(), str(target))
                    if u.fragment and target.suffix == '.html':
                        self.assertIsNotNone(doc(target).find(id=unquote(u.fragment)), value)
                schemas = [json.loads(s.string) for s in page.select('script[type="application/ld+json"]')]
                faq = next((s for s in schemas if s.get('@type') == 'FAQPage'), None)
                if faq:
                    visible = {x.summary.get_text(strip=True): x.p.get_text(' ', strip=True) for x in page.select('.faq details')}
                    self.assertEqual(visible, {x['name']: x['acceptedAnswer']['text'] for x in faq['mainEntity']})

    def test_print_guidance_has_limits_and_worked_example(self):
        sizing = doc(ROOT / 'guides/how-big-should-a-qr-code-be-for-print/index.html')
        text = sizing.get_text(' ', strip=True)
        self.assertIn('29', text)
        self.assertIn('37', text)
        self.assertIn('codewords', text)
        self.assertIn('planning shortcut, not a scan guarantee', text)
        for wrong in ('hard minimum', 'Bigger is always safer', 'you are done', 'safe limits', 'minimum code width'):
            self.assertNotIn(wrong, text)
        troubleshooting = doc(ROOT / 'guides/why-wont-my-qr-code-scan/index.html')
        self.assertIsNotNone(troubleshooting.find(id='diagnose'))
        text = troubleshooting.get_text(' ', strip=True)
        for wrong in ('20 to 25 percent', 'I have watched a lot', 'number one killer', 'will not scan, full stop'):
            self.assertNotIn(wrong, text)
        self.assertIn('codewords', text)

    def test_checklist_pdf_is_one_page_and_matches_html(self):
        path = ROOT / 'resources/qr-print-checklist.pdf'
        with fitz.open(path) as pdf:
            self.assertEqual(len(pdf), 1)
            text = ' '.join(pdf[0].get_text().split())
            for phrase in ('Before you print', 'Check the destination', 'Keep the margin', 'Test the finished piece', 'Record the result'):
                self.assertIn(phrase, text)
                self.assertIn(phrase, doc(ROOT / 'resources/qr-print-checklist.html').get_text(' ', strip=True))
            self.assertNotIn('localhost', text)
            pdf[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(str(OUTPUT / 'checklist.png'))

    def test_pages_render_and_resource_journey_works(self):
        ctx = self.context()
        p = ctx.new_page()
        errors = []
        p.on('pageerror', lambda e: errors.append(str(e)))
        rows = []
        for route in ROUTES:
            with self.subTest(route=route):
                response = p.goto(self.base + route)
                self.assertEqual(response.status, 200)
                for width in (320, 390, 768, 1280):
                    p.set_viewport_size({'width': width, 'height': 844})
                    self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), route)
                for width in (390, 1280):
                    p.set_viewport_size({'width': width, 'height': 900})
                    p.screenshot(path=str(OUTPUT / (route.strip('/').replace('/', '-') + f'-{width}.png')), full_page=True)
                rows.append({'route': route, 'http': response.status, 'widths': [320, 390, 768, 1280]})
        p.goto(self.base + 'guides/')
        p.locator('a[href="#guests"]').click()
        p.locator('#guests a[href="qr-code-for-wifi/"]').click()
        p.locator('a[href="/resources/guest-wifi-sign.html"]').first.click()
        self.assertTrue(p.url.endswith('/resources/guest-wifi-sign.html'))
        p.goto(self.base + 'resources/qr-print-checklist.html')
        with p.expect_download() as info:
            p.get_by_role('link', name='Download checklist PDF').click()
        saved = OUTPUT / 'downloaded-checklist.pdf'
        info.value.save_as(saved)
        self.assertEqual(saved.read_bytes(), (ROOT / 'resources/qr-print-checklist.pdf').read_bytes())
        self.assertEqual(errors, [])
        (OUTPUT / 'render-results.json').write_text(json.dumps(rows, indent=2))

    def test_wifi_sign_real_export_print_and_privacy(self):
        ctx = self.context()
        p = ctx.new_page()
        p.goto(self.base)
        p.locator('#tab-wifi').click()
        p.locator('#wifi-ssid').fill('Example Guest')
        p.locator('#wifi-pass').fill('Synthetic-Only-42')
        p.wait_for_timeout(500)
        with p.expect_download() as info:
            p.get_by_role('button', name='Download PNG', exact=True).click()
        qr = OUTPUT / 'synthetic-wifi.png'
        info.value.save_as(qr)
        payload = zxingcpp.read_barcode(Image.open(qr)).text
        self.assertIn('Example Guest', payload)
        p.goto(self.base + 'resources/guest-wifi-sign.html')
        self.assertTrue(p.locator('#print-sign').is_disabled())
        requests = []
        p.on('request', lambda r: requests.append(r.url))
        p.locator('#network-name').fill('Example Guest')
        p.locator('#qr-file').set_input_files(str(qr))
        p.wait_for_function('document.querySelector("#sign-qr").naturalWidth > 0')
        self.assertTrue(p.locator('#print-sign').is_disabled())
        p.locator('#confirm-test').check()
        self.assertTrue(p.locator('#print-sign').is_enabled())
        p.evaluate('window.print = () => { window.didPrint = true; }')
        p.locator('#print-sign').focus()
        p.keyboard.press('Enter')
        self.assertTrue(p.evaluate('window.didPrint'))
        self.assertEqual(p.locator('#sign-network').inner_text(), 'Example Guest')
        for width in (390,1280):
            p.set_viewport_size({'width':width,'height':900})
            p.screenshot(path=str(OUTPUT / f'wifi-filled-{width}.png'), full_page=True)
        p.emulate_media(media='print')
        p.pdf(path=str(OUTPUT / 'synthetic-wifi-sign.pdf'), format='Letter', print_background=True, display_header_footer=False)
        with fitz.open(OUTPUT / 'synthetic-wifi-sign.pdf') as pdf:
            self.assertEqual(len(pdf), 1)
            self.assertIn('Example Guest', pdf[0].get_text())
            pix = pdf[0].get_pixmap(matrix=fitz.Matrix(2,2))
            image = Image.open(io.BytesIO(pix.tobytes('png')))
            image.save(OUTPUT / 'wifi-print.png')
            actual = zxingcpp.read_barcode(image)
            self.assertIsNotNone(actual)
            self.assertEqual(actual.text, payload)
        p.emulate_media(media='screen')
        p.locator('#network-name').fill('x' * 64)
        self.assertFalse(p.locator('#confirm-test').is_checked())
        self.assertTrue(p.locator('#print-sign').is_disabled())
        p.set_viewport_size({'width': 320, 'height':844})
        self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
        self.assertEqual(requests, [])
        self.assertEqual(p.evaluate('localStorage.length + sessionStorage.length'), 0)
        p.locator('#clear-sign').click()
        self.assertTrue(p.locator('#print-sign').is_disabled())
        self.assertFalse(p.locator('#sign-qr').is_visible())
        self.assertEqual(p.locator('#network-name').input_value(), '')

    def test_wifi_sign_rejects_bad_images_and_recovers(self):
        p = self.context().new_page()
        p.goto(self.base + 'resources/guest-wifi-sign.html')
        for name, mime, data in [('bad.png','image/png',b'not an image'), ('bad.svg','image/svg+xml',b'<svg onload="alert(1)"></svg>'), ('huge.png','image/png',b'x' * (5*1024*1024+1))]:
            p.locator('#qr-file').set_input_files({'name':name,'mimeType':mime,'buffer':data})
            p.wait_for_function('document.querySelector("#file-error").textContent.length > 0')
            self.assertTrue(p.locator('#print-sign').is_disabled())
            self.assertEqual(p.locator('#qr-file').get_attribute('aria-invalid'), 'true')
        img = io.BytesIO()
        Image.new('RGB',(500,500),'white').save(img, format='PNG')
        p.locator('#qr-file').set_input_files({'name':'plain.png','mimeType':'image/png','buffer':img.getvalue()})
        p.wait_for_function('document.querySelector("#sign-qr").naturalWidth > 0')
        self.assertEqual(p.locator('#file-error').inner_text(), '')
        self.assertIn('does not verify', p.locator('#file-help').inner_text())
        self.assertTrue(p.locator('#print-sign').is_disabled())
        p.locator('#clear-sign').click()
        p.emulate_media(media='print')
        self.assertTrue(p.locator('#print-warning').is_visible())
        self.assertFalse(p.locator('#sign-sheet').is_visible())

if __name__ == '__main__':
    unittest.main(verbosity=2)
