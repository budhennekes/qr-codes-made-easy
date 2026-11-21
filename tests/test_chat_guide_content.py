"""Factual chat-guide regressions; run with the guide test environment."""
import json
from pathlib import Path
import unittest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def guide(slug):
    return BeautifulSoup((ROOT / 'guides' / slug / 'index.html').read_text(), 'html.parser')


class ChatGuideTests(unittest.TestCase):
    def test_faq_and_article_match_visible_content(self):
        for slug in ('qr-code-for-telegram', 'qr-code-for-whatsapp'):
            with self.subTest(slug=slug):
                doc = guide(slug)
                schemas = [json.loads(s.string) for s in doc.select('script[type="application/ld+json"]')]
                faq = next(s for s in schemas if s['@type'] == 'FAQPage')
                self.assertEqual(
                    {d.summary.get_text(strip=True): d.p.get_text(' ', strip=True) for d in doc.select('.faq details')},
                    {q['name']: q['acceptedAnswer']['text'] for q in faq['mainEntity']})
                article = next(s for s in schemas if s['@type'] == 'Article')
                self.assertEqual(article['description'], doc.select_one('meta[name=description]')['content'])
                self.assertEqual(article['datePublished'], '2026-07-09')
                self.assertEqual(article['dateModified'], '2026-10-27')
                self.assertIn('Updated October 27, 2026.', doc.select_one('.byline').get_text())
                self.assertIn('expiry', doc.select_one('.answer').get_text())
                self.assertNotIn('never expires', doc.get_text(' ', strip=True))

    def test_telegram_draft_and_privacy_are_not_absolute(self):
        doc = guide('qr-code-for-telegram')
        text = doc.get_text(' ', strip=True)
        self.assertNotIn('Telegram links cannot pre-type', text)
        self.assertNotIn('A username link never shows', text)
        self.assertIn('if the visitor can write', text)
        self.assertIn('Website link', text)
        self.assertIn('privacy settings', text)
        self.assertIn('https://t.me/yourusername?text=Hi%2C%20I%20saw%20your%20flyer', text)
        self.assertIsNotNone(doc.select_one('a[href="https://core.telegram.org/api/links#public-username-links"]'))

    def test_whatsapp_requires_active_account_and_visitor_send(self):
        doc = guide('qr-code-for-whatsapp')
        text = doc.get_text(' ', strip=True)
        self.assertIn('active WhatsApp account', doc.select_one('.answer').get_text())
        self.assertIn('scanning does not send a message automatically', text)
        self.assertNotIn('Scan it in three years', text)
        self.assertNotIn('more people actually hit send', text)
        self.assertIsNotNone(doc.select_one('a[href="https://faq.whatsapp.com/5913398998672934"]'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
