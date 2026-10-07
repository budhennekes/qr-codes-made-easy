"""Modern Minimal: all public pages, self-hosted fonts, and real computed contrast."""
import functools
import http.server
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import unittest
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('QR_THEME_QA_OUTPUT',str(ROOT.parent/'qr-optimization-qa/modern-minimal-20261006/local')))
PAGES=[f for f in subprocess.check_output(['git','ls-files','*.html'],cwd=ROOT,text=True).splitlines() if '.!' not in f and not f.startswith('google')]
SHOTS={'index.html':'generator','guides/index.html':'hub','guides/qr-code-for-wifi/index.html':'guide','for/restaurants/index.html':'industry','tools/qr-code-size-calculator/index.html':'calculator','resources/guest-wifi-sign.html':'sign','resources/qr-print-checklist.html':'checklist','privacy/index.html':'privacy'}

def contrast(a,b):
    def lum(s):
        v=[float(x)/255 for x in re.findall(r'[\d.]+',s)[:3]]
        return sum(w*(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4) for w,x in zip((.2126,.7152,.0722),v))
    x,y=sorted([lum(a),lum(b)])
    return (y+.05)/(x+.05)

class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,format,*args): pass
        OUT.mkdir(parents=True,exist_ok=True)
        cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.base=os.environ.get('QR_THEME_BASE_URL',f'http://127.0.0.1:{cls.server.server_port}/')
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch()
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close()
    def page(self):
        ctx=self.browser.new_context(reduced_motion='reduce');self.addCleanup(ctx.close)
        ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(self.base) else r.abort())
        return ctx.new_page()
    def test_all_pages_use_shared_or_embedded_theme(self):
        self.assertEqual(len(PAGES),36)
        for path in PAGES:
            text=(ROOT/path).read_text()
            with self.subTest(page=path):
                self.assertNotIn('fonts.googleapis.com',text)
                self.assertNotIn('fonts.gstatic.com',text)
                if path.startswith('resources/'):
                    self.assertIn('id="modern-minimal-theme"',text)
                    self.assertIn('data:font/woff2;base64,',text)
                else:
                    self.assertIn('/assets/modern-minimal.css?v=20261006',text)
    def test_every_page_renders_in_theme_at_phone_and_desktop(self):
        p=self.page();results=[]
        for path in PAGES:
            route=path[:-10] if path.endswith('index.html') else path
            for width in (390,1280):
                with self.subTest(page=path,width=width):
                    p.set_viewport_size({'width':width,'height':960})
                    response=p.goto(self.base+route)
                    self.assertEqual(response.status,200)
                    p.evaluate('document.fonts.ready')
                    actual=p.evaluate('''() => ({font:getComputedStyle(document.body).fontFamily,loaded:[...document.fonts].some(f=>f.family==='Inter'&&f.status==='loaded'),bg:getComputedStyle(document.body).backgroundColor,overflow:document.documentElement.scrollWidth>innerWidth+1,h1:getComputedStyle(document.querySelector('h1')).fontFamily})''')
                    self.assertIn('Inter',actual['font']);self.assertIn('Inter',actual['h1'])
                    self.assertTrue(actual['loaded']);self.assertEqual(actual['bg'],'rgb(255, 255, 255)')
                    self.assertFalse(actual['overflow'])
                    results.append({'page':path,'width':width,**actual})
                    if path in SHOTS:
                        p.screenshot(path=str(OUT/f'{SHOTS[path]}-{width}.png'))
                        if path=='index.html':
                            p.locator('#tool').scroll_into_view_if_needed()
                            p.screenshot(path=str(OUT/f'generator-tool-{width}.png'))
        (OUT/'render-results.json').write_text(json.dumps(results,indent=2))
    def test_actual_primary_button_and_muted_text_contrast(self):
        p=self.page()
        for route,selector in [('', '.btn-primary'),('guides/','.qr-demo'),('for/restaurants/','.btn-main'),('resources/qr-print-checklist.html','button')]:
            p.goto(self.base+route)
            colors=p.locator(selector).first.evaluate('(e)=>({a:getComputedStyle(e).color,b:getComputedStyle(e).backgroundColor})')
            self.assertGreaterEqual(contrast(colors['a'],colors['b']),4.5,(route,colors))
        for route,selector in [('', '.field'),('tools/qr-code-size-calculator/','select'),('resources/guest-wifi-sign.html','input[type=text]')]:
            p.goto(self.base+route)
            colors=p.locator(selector).first.evaluate('(e)=>({a:getComputedStyle(e).borderTopColor,b:getComputedStyle(e).backgroundColor})')
            self.assertGreaterEqual(contrast(colors['a'],colors['b']),3,(route,colors))
        p.goto(self.base)
        vals=p.evaluate('''()=>{const s=getComputedStyle(document.documentElement);return {muted:s.getPropertyValue('--ink-soft').trim(),bg:s.getPropertyValue('--paper-deep').trim()}}''')
        def rgb(h): return 'rgb('+','.join(str(int(h[i:i+2],16)) for i in (1,3,5))+')'
        self.assertGreaterEqual(contrast(rgb(vals['muted']),rgb(vals['bg'])),4.5)
    def test_calculator_control_and_keyboard_focus(self):
        p=self.page();p.goto(self.base+'tools/qr-code-size-calculator/')
        before=p.locator('#size').inner_text()
        p.locator('#distance').select_option('48')
        self.assertNotEqual(p.locator('#size').inner_text(),before)
        p.locator('#distance').focus()
        p.keyboard.press('Tab');p.keyboard.press('Shift+Tab')
        self.assertEqual(p.locator('#distance').evaluate('(e)=>getComputedStyle(e).outlineStyle'),'solid')
    def test_narrow_viewport_and_enlarged_text(self):
        p=self.page()
        for route in ('','guides/','resources/guest-wifi-sign.html','tools/qr-code-size-calculator/'):
            p.set_viewport_size({'width':320,'height':900});p.goto(self.base+route)
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),route)
        p.set_viewport_size({'width':1280,'height':1000});p.goto(self.base+'guides/')
        p.evaluate("document.documentElement.style.zoom='2'")
        self.assertTrue(p.locator('.primary-link').is_visible())
        self.assertTrue(p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))

if __name__=='__main__':unittest.main(verbosity=2)
