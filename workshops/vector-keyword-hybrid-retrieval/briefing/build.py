#!/usr/bin/env python3
"""Build index.html: the 15-slide Briefing deck, elastic-web kit style, ONE self-contained file, zero runtime network.

Network is used ONLY here, at build time, to fetch Inter / IBM Plex Mono woff2 once (cached in ./fonts).
Inputs: src/deck.css, src/player.js, src/slides/NN-*.html, notes/NN-*.md, the elastic-web kit (read only), briefing-data/data.json
"""
import base64, collections, glob, html as htmllib, json, math, os, random, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, 'vendor')  # elastic-web kit eweb.css / eweb.js, vendored
DATA = os.path.join(HERE, 'data', 'data.json')  # from tools/gather_data.py
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
read = lambda p: open(p, encoding='utf-8').read()
D = json.load(open(DATA))

# ---------------------------------------------------------------- fonts (base64 @font-face)
def fonts_css():
    fd = os.path.join(HERE, 'fonts'); os.makedirs(fd, exist_ok=True)
    gcss = os.path.join(fd, 'g.css')
    if not os.path.exists(gcss):
        url = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap'
        open(gcss, 'wb').write(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA})).read())
    css = read(gcss)
    blocks = re.findall(r'/\* ([\w-]+) \*/\s*@font-face\s*\{(.*?)\}', css, flags=re.S)
    out = []
    for subset, body in blocks:
        fam = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        wt = re.search(r'font-weight:\s*(\d+)', body).group(1)
        u = re.search(r'url\((https[^)]+)\)', body).group(1)
        rng = re.search(r'unicode-range:\s*([^;]+);', body).group(1)
        if not (subset == 'latin' or (fam == 'Inter' and subset == 'greek')):
            continue
        if fam == 'Inter':
            if wt != '400': continue            # Inter is one variable file: declare the whole weight range once
            wspec = '400 600'
        else:
            wspec = wt
        fn = os.path.join(fd, re.sub(r'\W+', '_', f'{fam}-{subset}-{wt}') + '.woff2')
        if not os.path.exists(fn):
            open(fn, 'wb').write(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA})).read())
        b64 = base64.b64encode(open(fn, 'rb').read()).decode()
        out.append("@font-face{font-family:'%s';font-style:normal;font-weight:%s;font-display:block;"
                   "src:url(data:font/woff2;base64,%s) format('woff2');unicode-range:%s}" % (fam, wspec, b64, rng))
    return '\n'.join(out)

# ---------------------------------------------------------------- kit css / js (kit itself is never modified)
def eweb_css():
    css = read(os.path.join(KIT, 'eweb.css'))
    css = re.sub(r"@import url\([^)]*\);\n?", '', css)                 # no Google Fonts
    css = re.sub(r'html\{[^}]*\}\n?', 'html{background:#fff;width:100%;height:100%;overflow:hidden}\n', css, count=1)
    css = css.replace('body{width:1280px;height:720px;overflow:hidden;position:absolute;background:#fff;color:var(--ink);',
                      '.slide{display:none;width:1280px;height:720px;overflow:hidden;position:absolute;left:0;top:0;background:#fff;color:var(--ink);')
    css = css.replace('body.soft{', '.slide.soft{').replace('body.ink{', '.slide.ink{').replace('body.ink .ew-foot', '.slide.ink .ew-foot')
    css += '\n.slide.on{display:block}\n'
    return css

def eweb_js():
    js = read(os.path.join(KIT, 'eweb.js'))
    js = re.sub(r"\n\s*document\.addEventListener\('DOMContentLoaded'.*?\);\n", '\n', js)   # player does chrome + fit
    assert 'DOMContentLoaded' not in js
    return js

# ---------------------------------------------------------------- shared data
CLUSTER_NAMES = ['Data lifecycle', 'Cluster ops', 'Security & auth', 'Analytics', 'Search & vectors', 'Config & versions', 'Memory & crashes']
CLUSTER_COL = ['#02BCB7', '#343741', '#FF957D', '#FEC514', '#0B64DD', '#B5BFCE', '#F04E98']   # kit palette only

# ---------------------------------------------------------------- 3D data for slides 05 and 07 (real data.json, scaled for the canvas engine)
SX, SY, SZ = 1.15, .72, 1.15
def T(v): return [round(v[0] * SX, 4), round(v[1] * SY, 4), round(v[2] * SZ, 4)]

def data05():
    docs = D['docs']; q = D['queries'][2]
    idx = {d['id']: i for i, d in enumerate(docs)}
    return json.dumps({
        'pts': [T(d['xyz']) + [d['cluster']] for d in docs],
        'q': T(q['xyz']),
        'near': [idx[n['id']] for n in q['nearest_docs']],
        'cos': [n['cos'] for n in q['nearest_docs']],
        'colors': CLUSTER_COL, 'names': CLUSTER_NAMES,
    })

def data07():
    ch = D['chunks']; cen = D['centroids']
    qraw = D['queries'][3]['xyz']
    P = [T(c['xyz']) for c in ch]; Q = T(qraw); C = [T(c) for c in cen]
    adj = collections.defaultdict(set)
    for a, b in D['edges']: adj[a].add(b); adj[b].add(a)
    dq = lambda i: math.dist(P[i], Q)
    def walk(s0):
        path, cur = [s0], s0
        while True:
            nb = min(adj[cur], key=dq)
            if dq(nb) < dq(cur) - 1e-9: path.append(nb); cur = nb
            else: break
        return path
    best = None
    for s0 in range(len(ch)):
        p = walk(s0)
        if len(p) < 7 or dq(p[-1]) > .08: continue
        score = (len(p) >= 8, dq(s0))               # long walk, far entry point
        if best is None or score > best[0]: best = (score, p)
    path = best[1]
    touched, seen = [], set()
    rej = []
    for k, n in enumerate(path):
        seen |= {n} | adj[n]
        touched.append(len(seen))
        nxt = path[k + 1] if k + 1 < len(path) else None
        rej.append([m for m in sorted(adj[n]) if m != nxt and m not in path[:k + 1]])
    looked = set(path)
    for i in path: looked |= adj[i]
    # edges to draw: everything the walk looked at, plus a light sample of the rest of the graph
    rnd = random.Random(5)
    others = [e for e in D['edges'] if e[0] not in looked and e[1] not in looked]
    samp = rnd.sample(others, 90)
    order = sorted(range(7), key=lambda k: math.dist(T(qraw), C[k]))
    lit = order[:2]
    n_disk = sum(1 for c in ch if c['cluster'] in lit)
    rad = []
    for k in range(7):
        ds = [math.dist(P[i], C[k]) for i, c in enumerate(ch) if c['cluster'] == k]
        rad.append(round(sum(ds) / len(ds), 3))
    flat_order = sorted(range(len(ch)), key=dq)
    info = dict(n_flat=len(ch), n_hnsw=len(looked), n_disk=n_disk, hops=len(path) - 1)
    print('slide07 data:', info, 'path', path, 'lit', lit)
    data = {'pts': [P[i] + [ch[i]['cluster']] for i in range(len(ch))], 'q': Q, 'cen': C, 'rad': rad,
            'path': path, 'touched': touched, 'rej': rej, 'samp': samp, 'lookedEdges': [[n, m] for n in path for m in sorted(adj[n])],
            'lit': lit, 'order': flat_order, 'colors': CLUSTER_COL, 'names': CLUSTER_NAMES, 'nFlat': len(ch), 'nHnsw': len(looked), 'nDisk': n_disk}
    return json.dumps(data), info

# ---------------------------------------------------------------- slide 09: illustrative 64x16 = 1,024 cells
def grid09():
    rnd = random.Random(11)
    cells = []
    for r in range(16):
        for c in range(64):
            bit = 1 if rnd.random() < .5 else 0
            op = .45 + rnd.random() * .55
            cells.append('<rect class="cell b%d" style="--o:%.2f" x="%d" y="%d" width="9.5" height="9.5"/>' % (bit, op, c * 11, r * 11))
    return '<g id="cells">' + ''.join(cells) + '</g>'

# ---------------------------------------------------------------- notes (md -> small html)
def md_inline(t):
    t = htmllib.escape(t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<i>\1</i>', t)
    t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
    return t

def notes_html(path):
    if not os.path.exists(path): return ''
    out = []
    for ln in read(path).splitlines():
        ln = ln.strip()
        if not ln or ln.startswith('# '): continue
        out.append('<p>%s</p>' % md_inline(ln))
    return '\n'.join(out)

NAV = ('<nav id="bar" aria-label="Slide navigation">'
       '<button id="btn-prev" type="button" aria-label="Previous"><svg class="arw rev" viewBox="0 0 24 12" aria-hidden="true"><path d="M0 6h20M15 1l6 5-6 5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>Prev</button>'
       '<span id="count" aria-live="polite">1 / 1</span>'
       '<span class="sp"></span>'
       '<button id="btn-overview" type="button" aria-label="Overview of all slides (O)" aria-haspopup="dialog"><svg viewBox="0 0 14 14" aria-hidden="true"><path d="M1 1h5v5H1zM8 1h5v5H8zM1 8h5v5H1zM8 8h5v5H8z" fill="currentColor"/></svg>Overview</button>'
       '<span class="sp"></span>'
       '<button id="btn-next" type="button" aria-label="Next">Next<svg class="arw" viewBox="0 0 24 12" aria-hidden="true"><path d="M0 6h20M15 1l6 5-6 5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></button>'
       '</nav>\n'
       '<div id="overview" role="dialog" aria-modal="true" aria-label="All slides" hidden><div class="ovh">All slides <span>Click a tile, or press Esc</span></div><div class="ovg" id="ovg"></div></div>\n')
ARW = '<svg class="arw" viewBox="0 0 24 12" aria-hidden="true"><path d="M0 6h20M15 1l6 5-6 5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'
STAR = '<svg class="star" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1.5l3.1 6.6 7.2.9-5.3 5 1.4 7.1L12 17.6l-6.4 3.5L7 14l-5.3-5 7.2-.9z" fill="currentColor"/></svg>'

# ---------------------------------------------------------------- assemble
ALLOWED = set(range(0x20, 0x7F)) | set(range(0xA0, 0x100)) | set(range(0x2000, 0x2070)) | {0x3A3, 0x20AC, 0x2122, 0x2191, 0x2193, 0x2212}

def main():
    d05 = data05()
    d07, info07 = data07()
    mark = re.search(r"EW\.MARK = '(.*?)';", eweb_js()).group(1)
    files = sorted(glob.glob(os.path.join(HERE, 'src', 'slides', '*.html')))
    slides, warn = [], []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        h = read(f)
        h = (h.replace('{{D05}}', d05).replace('{{D07}}', d07).replace('{{grid09}}', grid09())
              .replace('{{ARW}}', ARW).replace('{{STAR}}', STAR)
              .replace('{{N_FLAT}}', str(info07['n_flat'])).replace('{{N_HNSW}}', str(info07['n_hnsw'])).replace('{{N_DISK}}', str(info07['n_disk'])))
        foot = re.search(r'data-foot="([^"]*)"', h).group(1)
        chrome = ('<div class="ew-foot"><span class="lg">%s elastic</span><span class="rt"><span>%s</span></span></div>' % (mark, htmllib.escape(foot)))
        notes = notes_html(os.path.join(HERE, 'notes', base + '.md'))
        if not notes: warn.append('no notes for ' + base)
        h = h.replace('</section>', chrome + '\n<aside class="nt">' + notes + '</aside>\n</section>')
        slides.append(h)
        vis = re.sub(r'<(script|style)\b.*?</\1>', '', h, flags=re.S)
        vis = re.sub(r'<svg class="iso".*?</svg>', '', vis, flags=re.S)
        vis = htmllib.unescape(re.sub(r'<[^>]+>', ' ', vis))
        bad = sorted({c for c in vis if ord(c) not in ALLOWED and c not in '\n\t'})
        if bad: warn.append('%s: glyphs outside embedded fonts: %s' % (base, ' '.join('U+%04X' % ord(c) for c in bad)))
        if '—' in vis: warn.append(base + ': em dash')
    html = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>Vector search: the briefing</title>\n'
            '<style>\n' + fonts_css() + '\n' + eweb_css() + '\n' + read(os.path.join(HERE, 'src', 'deck.css')) + '\n</style>\n</head>\n<body>\n'
            '<div id="stage">\n' + '\n'.join(slides) + '\n</div>\n'
            + NAV +
            '<aside id="notes"><div class="nh"><span>Speaker notes</span><span id="notes-n"></span></div><div id="notes-body"></div><div class="nf">N to hide</div></aside>\n'
            '<script>\n' + eweb_js() + '\n</script>\n'
            '<script>\n' + read(os.path.join(HERE, 'src', 'engine3d.js')) + '\n</script>\n'
            '<script>\n' + read(os.path.join(HERE, 'src', 'player.js')) + '\n</script>\n</body>\n</html>\n')
    open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8').write(html)
    print('index.html', len(html) // 1024, 'KB;', len(slides), 'slides; slide07', info07)
    for w in warn: print('WARN', w)

if __name__ == '__main__':
    main()
