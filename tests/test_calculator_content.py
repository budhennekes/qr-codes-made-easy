"""Content, arithmetic, schema and browser regressions for the print-size tool."""
import functools,http.server,threading,unittest,json,re,os
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('QR_CALCULATOR_OUTPUT',str(ROOT.parent/'qr-optimization-qa/keyword-refresh-20261006/qa')))
ROUTE='tools/qr-code-size-calculator/'
class CalculatorContentTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  class Quiet(http.server.SimpleHTTPRequestHandler):
   def log_message(self,format,*args):pass
  cls.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
  threading.Thread(target=cls.server.serve_forever,daemon=True).start()
  cls.base=f'http://127.0.0.1:{cls.server.server_port}/';cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch();OUT.mkdir(parents=True,exist_ok=True)
 @classmethod
 def tearDownClass(cls):
  cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close()
 def page(self,width=1280):
  c=self.browser.new_context(viewport={'width':width,'height':960},reduced_motion='reduce');self.addCleanup(c.close)
  c.route('**/*',lambda r:r.continue_() if r.request.url.startswith(self.base) else r.abort())
  p=c.new_page();p.goto(self.base+ROUTE);return p
 def test_answer_metadata_and_honest_limits(self):
  d=BeautifulSoup((ROOT/ROUTE/'index.html').read_text(),'html.parser');text=d.get_text(' ',strip=True)
  self.assertEqual(len(d.select('h1')),2) # Main heading plus print-only worksheet heading.
  self.assertEqual(d.select_one('main h1').get_text(' ',strip=True),'QR code size calculator')
  self.assertLessEqual(len(d.title.string),60);self.assertLessEqual(len(d.find('meta',attrs={'name':'description'})['content']),155)
  for phrase in ['not a QR standard','four modules','before its blank margin','pixels per inch','not printed at the dimensions']:
   self.assertIn(phrase,text)
  self.assertNotIn('safe floor',text);self.assertNotIn('safe starting',text)
  self.assertEqual(d.select_one('link[rel=canonical]')['href'],'https://qrcodemadeeasy.com/'+ROUTE)
 def test_schema_matches_visible_faq_and_date(self):
  d=BeautifulSoup((ROOT/ROUTE/'index.html').read_text(),'html.parser')
  schema=[json.loads(x.string) for x in d.select('script[type="application/ld+json"]')]
  faq=next(x for x in schema if x['@type']=='FAQPage')
  actual=[(x.summary.get_text(' ',strip=True),x.p.get_text(' ',strip=True)) for x in d.select('.faq details')]
  self.assertEqual(actual,[(x['name'],x['acceptedAnswer']['text']) for x in faq['mainEntity']])
  page=next(x for x in schema if x['@type']=='WebPage');self.assertEqual(page['dateModified'],d.select_one('time')['datetime'])
 def test_worked_examples_match_the_live_calculator(self):
  p=self.page()
  for surface,distance,density,logo,expected in [('business-card','6','simple','no-logo',1),('flyer','12','simple','no-logo',1.5),('table-tent','24','simple','no-logo',2.5),('poster','48','simple','no-logo',5),('table-tent','24','dense','yes-logo',4)]:
   p.locator('#surface').select_option(surface);p.locator('#distance').select_option(distance);p.locator('label[for='+density+']').click();p.locator('label[for='+logo+']').click()
   self.assertEqual(float(p.locator('#size').inner_text().split()[0]),expected)
  self.assertIn('Planning for',p.locator('#distance-rule').inner_text());self.assertNotIn('safe starting',p.locator('#notice').inner_text())
 def test_table_math_and_margin_example(self):
  import math
  d=BeautifulSoup((ROOT/ROUTE/'index.html').read_text(),'html.parser')
  rows=d.select('.size-table tbody tr');self.assertEqual(len(rows),4)
  for row in rows:
   width=float(row['data-pattern-inches']);cells=row.find_all('td')
   self.assertEqual(cells[-1].get_text(strip=True),str(math.floor(width*25.4+.5))+' mm')
  total=2.5*37/29
  self.assertAlmostEqual(total,3.19,places=2);self.assertEqual(math.ceil(total*300),957)
  self.assertIn('957',d.select_one('.content').get_text())
 def test_responsive_links_and_print_worksheet(self):
  p=self.page()
  for width in [320,390,768,1280]:
   p.set_viewport_size({'width':width,'height':960});p.evaluate('document.fonts.ready')
   self.assertTrue(p.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   if width in [390,1280]:
    p.screenshot(path=str(OUT/f'calculator-{width}.png'))
    p.locator('#examples').scroll_into_view_if_needed();p.screenshot(path=str(OUT/f'examples-{width}.png'));p.evaluate('scrollTo(0,0)')
  for a in p.locator('.content a[href]').all():
   href=a.get_attribute('href')
   if href.startswith('/'):
    target=ROOT/href.lstrip('/').split('#')[0];self.assertTrue(target.exists(),href)
  p.emulate_media(media='print');p.pdf(path=str(OUT/'worksheet.pdf'),format='Letter',print_background=True)
  import pymupdf
  with pymupdf.open(OUT/'worksheet.pdf') as pdf:
   self.assertEqual(len(pdf),1);self.assertIn('not printed at the dimensions',pdf[0].get_text())
 def test_two_contextual_inbound_links(self):
  for f in ['guides/index.html','guides/how-big-should-a-qr-code-be-for-print/index.html']:
   d=BeautifulSoup((ROOT/f).read_text(),'html.parser');a=d.find('a',href='/'+ROUTE+'#examples');self.assertIsNotNone(a,f)
if __name__=='__main__':unittest.main(verbosity=2)
