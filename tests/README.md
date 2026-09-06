# Generator regression tests

Run from the repository root. Python 3.11+ and an isolated environment are required. These are development-only dependencies; the website still has no build step.

```sh
uv venv /tmp/qr-test-env
uv pip install --python /tmp/qr-test-env/bin/python playwright==1.62.0 pillow==12.3.0 zxing-cpp==3.1.1
PLAYWRIGHT_SKIP_BROWSER_GC=1 /tmp/qr-test-env/bin/python -m playwright install chromium
/tmp/qr-test-env/bin/python tests/test_generator.py
node --check generator.js
```

The suite starts a loopback-only HTTP server, uses a fresh Chromium context, and blocks third-party requests. It does not use a personal browser profile. Test URLs, contact details, and Wi-Fi values are synthetic. Screenshots and exports go to `/tmp/qr-code-qa`, or the directory set in `QR_QA_OUTPUT`.

Coverage:
- All six types: decode the preview and actual PNG and SVG exports with ZXing.
- Oversized content: no stale Ready state; block exports; recover after correction.
- Rapid typing: coalesce repeated encoding work.
- All style presets; logo upload and removal.
- Empty/invalid destination and keyboard tab navigation.
- Four-module minimum quiet zone in a short-link PNG.
- No horizontal overflow at 320, 390, 768, and 1280 CSS pixels; reduced-motion heading.

These are automated Chromium tests, not physical-phone or printer tests. Scan a printed proof with both iOS and Android before a major release. Native sharing, corrupt/large logo files, and all international phone formats require additional coverage.
