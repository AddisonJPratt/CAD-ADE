"""Assembly instructions: generated from the manifest, illustrated or checklist, HTML and PDF.

    XDG_CACHE_HOME=/tmp/cad-ade-cache .venv/bin/python -m unittest assembly.test_instructions -v
"""
import functools
import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
from PIL import Image

from assembly.gate import evaluate
from assembly.instructions import ACCENT, BUILT, browser, export, html, render_stage, steps
from assembly.manifest import FIXTURE, MANIFEST

ROOT = Path(__file__).resolve().parent.parent


@functools.cache
def holder():
    """The holder's manifest and meshes, written once by the gate into a fresh folder (read-only)."""
    out = Path(tempfile.mkdtemp())
    evaluate(ROOT / 'assembly' / 'holder_clip.py', ROOT, out=out)
    return json.loads((out / MANIFEST).read_text()), out


def share(path, colour):
    """Fraction of pixels within a few levels of a flat-shaded colour's hue (any shade)."""
    rgb = np.asarray(Image.open(path).convert('RGB'), dtype=float) / 255
    target = np.asarray(colour, dtype=float)
    lit = rgb.sum(axis=2) > 0.2
    unit = rgb / np.maximum(np.linalg.norm(rgb, axis=2, keepdims=True), 1e-9)
    return float(((unit @ (target / np.linalg.norm(target)) > 0.995) & lit & (rgb.std(axis=2) > 0.04)).mean())


HOLDER_STEPS = [   # the holder's steps as the committed manifest states them
    {'number': '1', 'text': 'Place the wall clip.', 'callout': None, 'tool': None},
    {'number': '2', 'text': 'Fasten the wall clip with 2 M3 x 12 mm screws into the mounting surface.',
     'callout': '2 × M3 socket-head screw, 12 mm', 'tool': 'hex key'},
]


class Page(HTMLParser):
    """Steps (data-step, with data-field children), images per step, and external references."""

    def __init__(self, text):
        super().__init__()
        self.steps, self.images, self.external, self.boxes = [], {}, [], 0
        self.field = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-step' in attrs:
            self.steps.append({'number': attrs['data-step'], 'text': None, 'callout': None, 'tool': None})
        if 'data-field' in attrs:
            self.field = attrs['data-field']
            self.steps[-1][self.field] = ''
        if tag == 'img' and self.steps:
            self.images.setdefault(self.steps[-1]['number'], []).append(attrs)
        if tag == 'input' and attrs.get('type') == 'checkbox':
            self.boxes += 1
        for key in ('src', 'href'):
            if attrs.get(key, '').startswith(('http:', 'https:', '//')):
                self.external.append(attrs[key])

    def handle_endtag(self, tag):
        self.field = None

    def handle_data(self, data):
        if self.field:
            self.steps[-1][self.field] += data.strip()


class Steps(unittest.TestCase):
    """The one step list both styles render, read from the committed holder manifest."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(FIXTURE.read_text())

    def test_holder_has_place_then_fasten(self):
        rows = steps(self.manifest)
        self.assertEqual([r['number'] for r in rows], [1, 2])
        self.assertEqual(rows[0]['tool'], None)
        self.assertEqual(rows[0]['callout'], None)
        self.assertEqual(rows[1]['tool'], 'hex key')
        self.assertEqual(rows[1]['callout'], '2 × M3 socket-head screw, 12 mm')

    def test_each_step_knows_what_is_new_and_what_is_already_built(self):
        rows = steps(self.manifest)
        self.assertEqual(rows[0]['new'], ['clip'])
        self.assertEqual(rows[0]['built'], [])
        self.assertEqual(rows[1]['new'], ['screw_1', 'screw_2'])
        self.assertEqual(rows[1]['built'], ['clip'])
        self.assertEqual(rows[1]['parts'], ['M3 screw 1', 'M3 screw 2'])



class StageImages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.folder = holder()
        cls.out = Path(tempfile.mkdtemp())

    def test_each_stage_is_rendered_with_the_new_parts_highlighted(self):
        first, second = steps(self.manifest)
        one, two = self.out / 'step-1.png', self.out / 'step-2.png'
        render_stage(self.manifest, self.folder, first, one)
        render_stage(self.manifest, self.folder, second, two)
        self.assertGreater(share(one, ACCENT), 0.02, 'step 1 shows the clip as the new part')
        self.assertLess(share(one, BUILT), 0.001, 'nothing is built before step 1')
        self.assertGreater(share(two, BUILT), 0.02, 'step 2 shows the clip as already built')
        self.assertGreater(share(two, ACCENT), 0.001, 'step 2 highlights the screws')



class Html(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.folder = holder()
        cls.illustrated = Page(html(cls.manifest, cls.folder))
        cls.checklist = Page(html(cls.manifest, cls.folder, style='checklist'))

    def test_both_styles_agree_step_for_step_with_the_manifest(self):
        self.assertEqual(self.illustrated.steps, HOLDER_STEPS)
        self.assertEqual(self.checklist.steps, HOLDER_STEPS)

    def test_illustrated_steps_each_have_an_embedded_stage_image_with_alt_text(self):
        for step in HOLDER_STEPS:
            images = self.illustrated.images.get(step['number'], [])
            self.assertEqual(len(images), 1, step['number'])
            self.assertTrue(images[0]['src'].startswith('data:image/png;base64,'))
            self.assertTrue(images[0].get('alt'))

    def test_checklist_is_compact_with_a_tick_box_per_step(self):
        self.assertEqual(self.checklist.images, {})
        self.assertEqual(self.checklist.boxes, len(HOLDER_STEPS))

    def test_pages_are_standalone(self):
        self.assertEqual(self.illustrated.external + self.checklist.external, [])

    def test_an_unknown_style_is_refused(self):
        with self.assertRaises(ValueError):
            html(self.manifest, self.folder, style='poster')



@unittest.skipUnless(browser() and shutil.which('pdftotext'), 'needs Chrome/Chromium and pdftotext')
class Export(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.folder = holder()
        cls.out = Path(tempfile.mkdtemp())
        cls.files = {style: export(cls.folder, cls.out, style=style) for style in ('illustrated', 'checklist')}

    def text(self, pdf):
        """The PDF's text with whitespace collapsed; a line wrapped after a hyphen is rejoined."""
        words = ' '.join(subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True,
                                        check=True).stdout.split())
        return words.replace('- ', '-')

    def test_each_style_writes_standalone_html_and_a_pdf_of_it(self):
        for style, files in self.files.items():
            self.assertEqual(files['html'].name, f'holder_clip-instructions-{style}.html')
            self.assertEqual(files['pdf'].name, f'holder_clip-instructions-{style}.pdf')
            self.assertEqual(Page(files['html'].read_text()).steps, HOLDER_STEPS)
            self.assertTrue(files['pdf'].read_bytes().startswith(b'%PDF'))

    def test_the_pdfs_carry_every_step_in_order_with_its_callout_and_tool(self):
        for style, files in self.files.items():
            text = self.text(files['pdf'])
            at = 0
            for step in HOLDER_STEPS:
                for field in ('text', 'callout', 'tool'):
                    if step[field]:
                        found = text.find(step[field], at)
                        self.assertGreaterEqual(found, 0, f'{style}: {step[field]!r} missing or out of order')
                        at = found



class Command(unittest.TestCase):
    def test_magic_py_instructions_writes_the_chosen_style(self):
        _, folder = holder()
        out = Path(tempfile.mkdtemp())
        done = subprocess.run([str(ROOT / '.venv' / 'bin' / 'python'), str(ROOT / 'magic.py'), 'instructions',
                               str(folder), '--style', 'checklist', '--out', str(out), '--no-pdf'],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['holder_clip-instructions-checklist.html'])
        self.assertEqual(Page((out / 'holder_clip-instructions-checklist.html').read_text()).steps, HOLDER_STEPS)

    def test_a_folder_without_a_manifest_is_an_error_not_a_traceback(self):
        done = subprocess.run([str(ROOT / '.venv' / 'bin' / 'python'), str(ROOT / 'magic.py'), 'instructions',
                               tempfile.mkdtemp(), '--no-pdf'], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(done.returncode, 2)
        self.assertIn('assembly.json', done.stderr)
        self.assertNotIn('Traceback', done.stderr)


if __name__ == '__main__':
    unittest.main()
