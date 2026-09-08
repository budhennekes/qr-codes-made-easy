"""Guide regression checks. No personal browser or third-party test requests."""
import functools
import http.server
import json
import os
from pathlib import Path
import threading
import unittest
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
GUIDES = sorted((ROOT / 'guides').glob('*/index.html'))
PAGES = [ROOT / 'guides/index.html', *GUIDES]
OUTPUT = Path(os.environ.get('QR_GUIDE_QA_OUTPUT', '/tmp/qr-guide-qa'))
BASE = os.environ.get('QR_GUIDE_BASE_URL', '')

def soup(path):
    return BeautifulSoup(path.read_text(), 'html.parser')

class GuideTests(unittest.TestCase):
    def test_featured_images_are_compact_and_originals_preserved(self):
        self.assertEqual(len(GUIDES), 20)
        for path in GUIDES:
            with self.subTest(page=str(path.relative_to(ROOT))):
                for image in soup(path).select('img.featured'):
                    asset = path.parent / image['src']
                    self.assertEqual(asset.suffix, '.webp')
                    self.assertTrue(asset.is_file())
                    self.assertLess(asset.stat().st_size, 60000)
                    with Image.open(asset) as actual, Image.open(path.parent / 'og.png') as original:
                        self.assertEqual(actual.size, (int(image['width']), int(image['height'])))
                        if path.parent.name != 'qr-code-for-linkedin':
                            self.assertIsNone(ImageChops.difference(actual.convert('RGBA'), original.convert('RGBA')).getbbox(alpha_only=False))
                    self.assertEqual(image.get('fetchpriority'), 'high')

    def test_guide_navigation_connects_generator_and_sizing(self):
        for path in PAGES:
            with self.subTest(page=str(path.relative_to(ROOT))):
                nav = soup(path).select_one('header nav')
                self.assertIsNotNone(nav.find('a', string='Generator'))
                sizing = nav.find('a', string='Print sizing')
                self.assertIsNotNone(sizing)
                self.assertEqual((path.parent / sizing['href']).resolve(), ROOT / 'tools/qr-code-size-calculator')

    def test_local_links_fragments_images_and_jsonld(self):
        for path in PAGES:
            with self.subTest(page=str(path.relative_to(ROOT))):
                doc = soup(path)
                self.assertEqual(len(doc.select('h1')), 1)
                self.assertTrue(doc.select_one('link[rel=canonical]')['href'].startswith('https://qrcodemadeeasy.com/'))
                for script in doc.select('script[type="application/ld+json"]'):
                    json.loads(script.string)
                for element in doc.select('a[href],img[src]'):
                    value = element.get('href', element.get('src'))
                    url = urlparse(urljoin('https://qrcodemadeeasy.com/' + str(path.relative_to(ROOT)), value))
                    if url.netloc != 'qrcodemadeeasy.com':
                        continue
                    target = ROOT / unquote(url.path).lstrip('/')
                    if target.is_dir():
                        target = target / 'index.html'
                    self.assertTrue(target.is_file(), str(target))
                    if url.fragment and target.suffix == '.html':
                        self.assertIsNotNone(soup(target).find(id=unquote(url.fragment)), value)

    def test_restaurant_content_and_faq_schema_agree(self):
        doc = soup(ROOT / 'guides/qr-code-for-a-restaurant-menu/index.html')
        self.assertIsNotNone(doc.find(id='proof'))
        self.assertIsNotNone(doc.find(id='menu-format'))
        self.assertNotIn('read scans in your own analytics', doc.get_text())
        self.assertIn('not an exact scan count', doc.get_text())
        visible = {x.summary.get_text(strip=True): x.p.get_text(' ', strip=True) for x in doc.select('.faq details')}
        schemas = [json.loads(x.string) for x in doc.select('script[type="application/ld+json"]')]
        faq = next(x for x in schemas if x.get('@type') == 'FAQPage')
        self.assertEqual(visible, {x['name']: x['acceptedAnswer']['text'] for x in faq['mainEntity']})

    def test_hub_does_not_promise_exact_scan_counts(self):
        text = soup(ROOT / 'guides/index.html').get_text(' ', strip=True)
        self.assertNotIn('Count your scans for free', text)
        self.assertNotIn('safe minimum size', text)
        self.assertIn('visits', text)

    def test_all_guide_pages_render_on_mobile(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
        OUTPUT.mkdir(parents=True, exist_ok=True)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = BASE or f'http://127.0.0.1:{server.server_port}/'
        rows = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                context = browser.new_context(viewport={'width': 390, 'height': 844})
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                for path in PAGES:
                    route = str(path.relative_to(ROOT)).removesuffix('index.html')
                    with self.subTest(route=route):
                        response = page.goto(urljoin(base, route))
                        self.assertEqual(response.status, 200)
                        page.wait_for_function('Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)')
                        for width in (320, 390, 1280):
                            page.set_viewport_size({'width': width, 'height': 844})
                            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        self.assertTrue(page.locator('header nav').get_by_role('link', name='Print sizing', exact=True).is_visible())
                        self.assertEqual(page.locator('h1').count(), 1)
                        if path.parent.name in ('guides', 'qr-code-for-a-restaurant-menu', 'qr-code-for-wifi'):
                            for width in (390, 1280):
                                page.set_viewport_size({'width': width, 'height': 844})
                                page.screenshot(path=str(OUTPUT / f'{path.parent.name}-{width}.png'), full_page=True)
                        rows.append({'route': route, 'status': response.status, 'widths': [320, 390, 1280]})
                page.goto(urljoin(base, 'guides/qr-code-for-a-restaurant-menu/'))
                page.locator('header nav').get_by_role('link', name='Print sizing', exact=True).click()
                self.assertIn('/tools/qr-code-size-calculator/', page.url)
                self.assertEqual(errors, [])
                context.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            (OUTPUT / 'guide-results.json').write_text(json.dumps(rows, indent=2))

if __name__ == '__main__':
    unittest.main(verbosity=2)
