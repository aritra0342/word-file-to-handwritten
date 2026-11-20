#!/usr/bin/env python3
"""Render text as handwritten-looking A4 pages and save them as a PDF.

Two ways to use it:

1. CLI, for plain prose:   python handwrite.py input.docx|.pdf|.txt|.md -o out.pdf
2. Library, for maths, tables and exact layouts:
       from handwrite import Doc
       d = Doc(paper='plain'); d.line(...); d.para(...); d.save('out.pdf')

Every letter is drawn separately with small random changes in size, tilt and
position, then the whole page is bent slightly so no two letters are identical.
Dependencies: pillow, numpy, scipy, fonttools, img2pdf (python-docx for Word input,
pdfplumber or pypdf for PDF input).
"""
import argparse, io, math, os, random, re, sys
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, '..', 'assets', 'fonts')
DEFAULT_FONT = os.path.join(FONT_DIR, 'Mali-Regular.ttf')
FALLBACK_FONT = os.path.join(FONT_DIR, 'PlaypenSans.ttf')   # Greek and maths symbols

W, H = 1654, 2339                       # A4 at 200 dpi
INKS = {'black': (20, 20, 26), 'blue': (24, 44, 120)}


def parse(text):
    """'x_{1}^{2}' -> [(char, level)], level -1 subscript, +1 superscript."""
    out, i, lvl = [], 0, 0
    while i < len(text):
        if text[i] in '_^' and text[i + 1:i + 2] == '{':
            lvl = -1 if text[i] == '_' else 1
            i += 2
            continue
        if text[i] == '}' and lvl:
            lvl = 0
            i += 1
            continue
        out.append((text[i], lvl))
        i += 1
    return out


class Style:
    def __init__(self, font=None, size=41, pitch=70, ink='black', paper='plain',
                 margins=(150, 110, 125, 110), frame=False, messiness=1.0):
        self.font = font or DEFAULT_FONT
        self.size, self.pitch = size, pitch
        self.ink = INKS.get(ink, INKS['black']) if isinstance(ink, str) else tuple(ink)
        self.paper, self.frame, self.mess = paper, frame, messiness
        self.ml, self.mr, self.mt, self.mb = margins
        self.cmap = TTFont(self.font, fontNumber=0).getBestCmap()
        self._fb_cmap = TTFont(FALLBACK_FONT).getBestCmap() if os.path.exists(FALLBACK_FONT) else {}
        self._cache = {}

    def path_for(self, ch):
        if ord(ch) in self.cmap or ord(ch) not in self._fb_cmap:
            return self.font
        return FALLBACK_FONT

    def get(self, path, px):
        k = (path, px)
        if k not in self._cache:
            f = ImageFont.truetype(path, px)
            if path == FALLBACK_FONT:
                try:
                    f.set_variation_by_axes([330])
                except Exception:
                    pass
            self._cache[k] = f
        return self._cache[k]

    def csize(self, ch, lvl, scale):
        s = self.size * scale * (0.62 if lvl else 1.0)
        return s * 0.80 if self.path_for(ch) != self.font else s

    def cwidth(self, ch, lvl=0, scale=1.0):
        if ch == '∴' and ord(ch) not in self.cmap:
            return self.size * scale * 0.62
        w = self.get(self.path_for(ch), int(round(self.csize(ch, lvl, scale)))).getlength(ch)
        return w * 1.25 if ch == ' ' else w

    def twidth(self, text, scale=1.0):
        return sum(self.cwidth(c, l, scale) for c, l in parse(text))


class Page:
    def __init__(self, style, seed):
        self.s, self.rng = style, random.Random(seed)
        self.ink = Image.new('L', (W, H), 0)
        self.pencil = Image.new('L', (W, H), 0)
        self.y = style.mt
        self.wo, self.ws = 0.0, 1.0
        self._newline()
        if style.frame:
            self._frame()

    # --- low level -------------------------------------------------------
    def _newline(self):
        r, m = self.rng, self.s.mess * (0.35 if self.s.paper == 'ruled' else 1.0)
        self.slope = r.gauss(-0.004, 0.006) * m
        self.amp, self.per, self.ph = r.uniform(1.5, 4.0) * m, r.uniform(260, 520), r.uniform(0, 6.28)
        self.xoff = r.gauss(0, 9) * self.s.mess

    def _base(self, x, y):
        return y + self.slope * (x - self.s.ml) + self.amp * math.sin(x / self.per + self.ph)

    def _glyph(self, ch, lvl, x, y, scale):
        r, s, m = self.rng, self.s, self.s.mess
        w = s.cwidth(ch, lvl, scale)
        if ch == ' ':
            self.wo, self.ws = r.gauss(0, 1.8) * m, r.gauss(1.0, 0.016 * m)
            return w * r.uniform(0.75, 1.35)
        yb = self._base(x, y) + r.gauss(0, 1.5) * m + self.wo
        if lvl == -1:
            yb += s.size * scale * 0.22
        if lvl == 1:
            yb -= s.size * scale * 0.42
        if ch == '∴' and ord(ch) not in s.cmap:
            d, z = ImageDraw.Draw(self.ink), s.size * scale
            for dx, dy in ((0.30, -0.52), (0.10, -0.16), (0.50, -0.16)):
                cx, cy = x + dx * z + r.gauss(0, 1), yb + dy * z + r.gauss(0, 1)
                d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=255)
            return w
        size = s.csize(ch, lvl, scale) * r.gauss(1.0, 0.016 * m) * self.ws
        f = s.get(s.path_for(ch), max(8, int(round(size))))
        pad, by = int(size), int(size * 1.5)
        tile = Image.new('L', (int(w) + 2 * pad, int(size * 2.4)), 0)
        ImageDraw.Draw(tile).text((pad, by), ch, font=f, fill=255, anchor='ls')
        tile = tile.rotate(r.gauss(0, 1.5) * m, resample=Image.BICUBIC, center=(pad + w / 2, by))
        px, py = int(round(x - pad)), int(round(yb - by))
        box = (px, py, px + tile.width, py + tile.height)
        self.ink.paste(ImageChops.lighter(self.ink.crop(box), tile), (px, py))
        return w + r.gauss(0, 1.3) * m

    def text(self, text, x, y, scale=1.0):
        """Draw text with its baseline at pixel (x, y). Returns the end x."""
        for ch, lvl in parse(text):
            x += self._glyph(ch, lvl, x, y, scale)
        return x

    def stroke(self, x0, y0, x1, y1, width=3, layer=None, jit=1.2):
        d, r = ImageDraw.Draw(layer or self.ink), self.rng
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 40))
        pts = [(x0 + (x1 - x0) * i / n + r.gauss(0, jit * 0.4), y0 + (y1 - y0) * i / n + r.gauss(0, jit))
               for i in range(n + 1)]
        d.line(pts, fill=255, width=width, joint='curve')

    def _frame(self):
        r = self.rng
        a = [(62, 70), (W - 60, 66), (W - 58, H - 70), (64, H - 66)]
        a = [(x + r.gauss(0, 3), y + r.gauss(0, 3)) for x, y in a]
        for i in range(4):
            self.stroke(*a[i], *a[(i + 1) % 4], width=2, layer=self.pencil, jit=0.5)

    # --- compositing -----------------------------------------------------
    def finish(self, seed):
        from scipy.ndimage import map_coordinates, zoom
        s, rs, g = self.s, np.random.RandomState(seed), 26
        amp = 1.9 * s.mess
        dx = zoom(rs.normal(0, 1, (H // g + 2, W // g + 2)), g, order=3)[:H, :W] * amp
        dy = zoom(rs.normal(0, 1, (H // g + 2, W // g + 2)), g, order=3)[:H, :W] * amp
        yy, xx = np.mgrid[0:H, 0:W]
        warped = map_coordinates(np.asarray(self.ink, dtype=np.float32), [yy + dy, xx + dx], order=1)
        ink = Image.fromarray(np.clip(warped, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
        a = np.asarray(ink, dtype=np.float32) / 255.0
        lo = Image.fromarray((rs.rand(H // 40 + 2, W // 40 + 2) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        a = np.clip(a * 1.9, 0, 1) * (0.80 + 0.20 * np.asarray(lo, dtype=np.float32) / 255.0)
        paper = np.ones((H, W, 3), np.float32) * np.array([249, 248, 244], np.float32)
        paper += rs.normal(0, 1.6, (H, W, 1)).astype(np.float32)
        lo2 = Image.fromarray((rs.rand(8, 6) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        paper += (np.asarray(lo2, dtype=np.float32) / 255.0 - 0.5)[..., None] * 7
        if s.paper == 'ruled':
            rule = Image.new('L', (W, H), 0)
            d = ImageDraw.Draw(rule)
            y = s.mt + s.size + 9
            while y < H - 40:
                d.line([(0, y), (W, y)], fill=255, width=2)
                y += s.pitch
            ra = np.asarray(rule, np.float32)[..., None] / 255.0 * 0.45
            paper = paper * (1 - ra) + np.array([150, 175, 215], np.float32) * ra
            mg = Image.new('L', (W, H), 0)
            ImageDraw.Draw(mg).line([(s.ml - 28, 0), (s.ml - 28, H)], fill=255, width=3)
            ma = np.asarray(mg, np.float32)[..., None] / 255.0 * 0.55
            paper = paper * (1 - ma) + np.array([225, 120, 130], np.float32) * ma
        out = paper * (1 - a[..., None]) + np.array(s.ink, np.float32) * a[..., None]
        pen = np.asarray(self.pencil.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0 * 0.38
        out = out * (1 - pen[..., None]) + np.array([95, 95, 100], np.float32) * pen[..., None]
        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


class Doc:
    """A multi-page handwritten document. Starts a new page automatically when one fills up.

    Positions (x, hang, column x) are fractions of the text width: 0.0 = left margin, 1.0 = right.
    Inline markup: _{..} subscript, ^{..} superscript.
    """

    def __init__(self, font=None, size=41, pitch=70, ink='black', paper='plain',
                 frame=False, messiness=1.0, seed=7):
        self.s = Style(font, size, pitch, ink, paper, frame=frame, messiness=messiness)
        self.seed, self.pages, self.p = seed, [], None
        self.new_page()

    # --- paging ----------------------------------------------------------
    def new_page(self):
        if self.p is not None:
            self.pages.append(self.p.finish(self.seed + len(self.pages)))
        self.p = Page(self.s, self.seed * 101 + len(self.pages))

    def _room(self, lines=1.0):
        if self.p.y + lines * self.s.pitch > H - self.s.mb:
            self.new_page()

    @property
    def _fw(self):
        return W - self.s.ml - self.s.mr

    def _adv(self, lines):
        if self.s.paper == 'ruled':
            lines = max(1, math.ceil(lines - 0.05))
        self.p.y += lines * self.s.pitch

    # --- blocks ----------------------------------------------------------
    def gap(self, lines=0.5):
        """Vertical space, in line heights."""
        if self.s.paper == 'ruled':
            lines = round(lines)
        self.p.y += lines * self.s.pitch

    def line(self, text, x=0.0, center=False, underline=False, box=False, scale=1.0):
        """One line, not wrapped. scale enlarges it (titles); box draws a rectangle round it."""
        self._room(scale)
        p, s = self.p, self.s
        p._newline()
        x0 = s.ml + x * self._fw + p.xoff
        if center:
            x0 = (W - s.twidth(text, scale)) / 2 + p.xoff
        if s.paper == 'ruled':
            yb = p.y + s.size + (math.ceil(scale - 0.05) - 1) * s.pitch
        else:
            yb = p.y + s.size * scale
        x1 = p.text(text, x0, yb, scale)
        if underline:
            yy = p._base(x0, yb) + 13
            p.stroke(x0 - 4, yy, x1 + 6, yy + p.rng.gauss(0, 3))
        if box:
            q, t, b = 14, yb - s.size * scale * 0.95, yb + 20
            p.stroke(x0 - q, t, x1 + q, t + p.rng.gauss(0, 2))
            p.stroke(x1 + q, t, x1 + q + p.rng.gauss(0, 2), b)
            p.stroke(x1 + q, b, x0 - q, b + p.rng.gauss(0, 2))
            p.stroke(x0 - q, b, x0 - q + p.rng.gauss(0, 2), t)
        self._adv(scale)

    def cols(self, items, underline=()):
        """Several pieces on one line: items = [(x, text), ...]. Use for tables and side-by-side maths."""
        self._room()
        p, s = self.p, self.s
        yb = p.y + s.size
        for i, (xf, t) in enumerate(items):
            p._newline()
            x0 = s.ml + xf * self._fw + p.xoff
            x1 = p.text(t, x0, yb)
            if i in underline:
                yy = p._base(x0, yb) + 13
                p.stroke(x0 - 4, yy, x1 + 6, yy + p.rng.gauss(0, 3))
        self._adv(1)

    def para(self, text, x=0.0, hang=None, label=None):
        """Word-wrapped paragraph. label (e.g. 'Q1)', 'Ans)') sits at x; the body starts at hang."""
        s = self.s
        hang = x if hang is None else hang
        left = s.ml + hang * self._fw
        maxw = W - s.mr - left
        cur, lines = [], []
        for wd in text.split():
            if cur and s.twidth(' '.join(cur + [wd])) > maxw * self.p.rng.uniform(0.93, 1.0):
                lines.append(' '.join(cur))
                cur = [wd]
            else:
                cur.append(wd)
        if cur:
            lines.append(' '.join(cur))
        for i, ln in enumerate(lines):
            self._room()
            p = self.p
            p._newline()
            if i == 0 and label:
                p.text(label, s.ml + x * self._fw + p.xoff, p.y + s.size)
                p._newline()
            p.text(ln, left + p.xoff, p.y + s.size)
            self._adv(1)

    def frac(self, prefix, num, den, suffix='', x=0.0):
        """prefix  num/den  suffix, written as a stacked fraction (takes about two lines)."""
        self._room(3 if self.s.paper == 'ruled' else 2.2)
        p, s = self.p, self.s
        ruled = s.paper == 'ruled'
        p._newline()
        if not ruled:
            p.y += 18
        yb = p.y + s.size + (s.pitch if ruled else 0)
        x0 = p.text(prefix, s.ml + x * self._fw + p.xoff, yb) + 14
        wn, wd = s.twidth(num), s.twidth(den)
        wm = max(wn, wd)
        p.text(num, x0 + (wm - wn) / 2, yb - 30)
        p.stroke(x0 - 6, yb - 14, x0 + wm + 8, yb - 14 + p.rng.gauss(0, 2))
        p.text(den, x0 + (wm - wd) / 2, yb + 36)
        if suffix:
            p.text(suffix, x0 + wm + 22, yb)
        p.y += 3 * s.pitch if ruled else s.pitch + 26

    def heading(self, text, level=1):
        """level 1: large centred title. level 2: underlined sub-heading at the left."""
        if level == 1:
            self.line(text, center=True, underline=True, scale=1.0 if self.s.paper == 'ruled' else 1.25)
        else:
            self.line(text, underline=True)
        self.gap(0.3)

    # --- output ----------------------------------------------------------
    def _all(self):
        return self.pages + [self.p.finish(self.seed + len(self.pages))]

    def save(self, path):
        import img2pdf
        pages, bufs = self._all(), []
        for im in pages:
            b = io.BytesIO()
            im.save(b, 'JPEG', quality=90, dpi=(200, 200))
            bufs.append(b.getvalue())
        a4 = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
        with open(path, 'wb') as f:
            f.write(img2pdf.convert(bufs, layout_fun=img2pdf.get_layout_fun(a4)))
        return len(pages)

    def preview(self, path, page=0):
        """Save one page as a PNG so the result can be looked at before delivering."""
        self._all()[page].save(path)

    # --- plain text / markdown -------------------------------------------
    def write_text(self, text):
        """Lay out simple text: '# ' title, '## ' sub-heading, '- ' or '1)' list items, blank line = new
        paragraph, '---' or form feed = new page. Leading spaces indent (4 spaces = one step)."""
        buf, indent = [], 0.0

        def flush():
            nonlocal buf
            if buf:
                self.para(' '.join(buf), x=indent)
                buf = []
        for raw in text.replace('\t', '    ').splitlines():
            if '\f' in raw or raw.strip() == '---':
                flush()
                self.new_page()
                continue
            st = raw.strip()
            if not st:
                flush()
                self.gap(0.4)
                continue
            ind = min(0.4, (len(raw) - len(raw.lstrip(' '))) // 4 * 0.05)
            m = re.match(r'^([-*•]|\(?[0-9]{1,2}[.)]|\(?[a-zA-Z][.)]|\(?[ivxIVX]{1,4}\))\s+(.*)$', st)
            if st.startswith('## '):
                flush()
                self.heading(st[3:], 2)
            elif st.startswith('# '):
                flush()
                self.heading(st[2:], 1)
            elif m:
                flush()
                lab = '-' if m.group(1) in '-*•' else m.group(1)
                hang = ind + max(0.035, self.s.twidth(lab + '  ') / self._fw)
                self.para(m.group(2), x=ind, hang=hang, label=lab)
            else:
                if buf and ind != indent:
                    flush()
                indent = ind
                buf.append(st)
        flush()


def pdf_to_text(path):
    """Extract text from a typed PDF, page by page."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = [pg.extract_text() or '' for pg in pdf.pages]
    except ImportError:
        from pypdf import PdfReader
        pages = [pg.extract_text() or '' for pg in PdfReader(path).pages]
    return '\n\f\n'.join(pages)


def docx_to_text(path):
    """Extract text from a Word file as the light markup write_text understands."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = docx.Document(path)
    out, num = [], 0
    for el in doc.element.body.iterchildren():
        tag = el.tag.rsplit('}', 1)[-1]
        if tag == 'p':
            p = Paragraph(el, doc)
            text = ' '.join(p.text.split())
            style = (p.style.name if p.style is not None else '').lower()
            if 'w:type="page"' in el.xml:
                out.append('---')
            if not text:
                out.append('')
                num = 0
                continue
            if style.startswith('title') or style == 'heading 1':
                out += ['', '# ' + text, '']
                num = 0
            elif style.startswith('heading'):
                out += ['', '## ' + text, '']
                num = 0
            elif 'list number' in style:
                num += 1
                out.append(f'{num}) {text}')
            elif 'list' in style or (el.pPr is not None and el.pPr.numPr is not None):
                out.append('- ' + text)
            else:
                out += [text, '']
                num = 0
        elif tag == 'tbl':
            out.append('')
            for row in Table(el, doc).rows:
                cells = []
                for c in row.cells:
                    t = ' '.join(c.text.split())
                    if not cells or t != cells[-1]:
                        cells.append(t)
                out += ['   '.join(cells), '']
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description='Turn a Word file, typed PDF or text file into a handwritten-looking PDF.')
    ap.add_argument('input', help='.docx, .pdf, .txt or .md')
    ap.add_argument('-o', '--output')
    ap.add_argument('--font', help='path to a .ttf/.otf handwriting font (e.g. one made from your own writing)')
    ap.add_argument('--paper', choices=['plain', 'ruled'], default='plain')
    ap.add_argument('--ink', default='black', help='black, blue, or R,G,B')
    ap.add_argument('--size', type=int, default=41, help='letter size in px at 200 dpi (default 41)')
    ap.add_argument('--pitch', type=int, default=70, help='line spacing in px (default 70)')
    ap.add_argument('--messiness', type=float, default=1.0, help='0 = very neat, 1 = natural, 1.5 = hurried')
    ap.add_argument('--frame', action='store_true', help='draw a pencil border round each page')
    ap.add_argument('--keep-pages', action='store_true', help='start a new page where the source PDF does')
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    ink = tuple(int(v) for v in a.ink.split(',')) if ',' in a.ink else a.ink
    is_pdf = a.input.lower().endswith('.pdf')
    low = a.input.lower()
    if low.endswith('.doc'):
        sys.exit('Old .doc files are not supported. Save the file as .docx in Word and try again.')
    if is_pdf:
        text = pdf_to_text(a.input)
    elif low.endswith('.docx'):
        text = docx_to_text(a.input)
    else:
        text = open(a.input, encoding='utf-8').read()
    if is_pdf and not a.keep_pages:
        text = text.replace('\f', '')
    if not text.strip():
        sys.exit('No text found. If the PDF is a scan or photo, transcribe it first and pass a .txt file.')
    out = a.output or re.sub(r'\.[^.]+$', '', a.input) + '_handwritten.pdf'
    d = Doc(a.font, a.size, a.pitch, ink, a.paper, a.frame, a.messiness, a.seed)
    d.write_text(text)
    print(f'Wrote {d.save(out)} page(s) to {out}')


if __name__ == '__main__':
    main()
