"""Build deployable versions of the web calculator.

dist/site/      full HTML document with CSS and JS inlined, plus data/ and img/  (drop into any web server)
dist/artifact/  the same page without the <html>/<head>/<body> wrapper, for a claude.ai artifact

The model data are copied from python/dsa_etc/data, so the browser and the Python package always share one set.
"""
import html as _html
import os, re, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WEB = os.path.join(ROOT, 'web')
DATA = os.path.join(ROOT, 'python', 'dsa_etc', 'data')
DIST = os.path.join(ROOT, 'dist')


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------- minimal Markdown renderer for the documentation views
# Supports: #-#### headings (with anchor ids), paragraphs, - and 1. lists (one level), pipe tables, indented (4-space)
# blocks rendered as equations, `code`, **bold**, *italic*, [text](href), and raw HTML (passed through).
def _slug(text, prefix):
    t = re.sub(r"<[^>]+>", "", text).lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return prefix + "-" + t


def _inline(t):
    t = re.sub(r"`([^`]+)`", lambda m: "<code>" + _html.escape(m.group(1), quote=False) + "</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    return t


def render_markdown(md, prefix):
    """Markdown -> (html, toc_html). Headings get ids prefix-slug; h2/h3 go into the contents list."""
    lines = md.split("\n")
    out, toc, i = [], [], 0
    para = []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            flush()
            lvl, text = len(m.group(1)), m.group(2).strip()
            hid = _slug(text, prefix)
            out.append('<h%d id="%s">%s</h%d>' % (lvl, hid, _inline(text), lvl))
            if lvl in (2, 3):
                toc.append((lvl, hid, re.sub(r"<[^>]+>", "", _inline(text))))
            i += 1
            continue
        if ln.startswith("    ") and not para:
            block = []
            while i < len(lines) and (lines[i].startswith("    ") or (lines[i].strip() == "" and i + 1 < len(lines)
                                                                      and lines[i + 1].startswith("    "))):
                block.append(lines[i][4:])
                i += 1
            out.append('<pre class="eq">' + _html.escape("\n".join(block), quote=False) + "</pre>")
            continue
        if ln.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            flush()
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            head = cells(ln)
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            t = '<div class="table-wrap"><table class="data"><thead><tr>' + "".join("<th>%s</th>" % _inline(h) for h in head)
            t += "</tr></thead><tbody>" + "".join("<tr>" + "".join('<td class="txt">%s</td>' % _inline(c) for c in r) + "</tr>"
                                               for r in rows) + "</tbody></table></div>"
            out.append(t)
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            flush()
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            items = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m and (("ol" if m.group(2)[0].isdigit() else "ul") != tag):
                    break
                if m:
                    items.append(m.group(3))
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            out.append("<%s>%s</%s>" % (tag, "".join("<li>" + _inline(it) + "</li>" for it in items), tag))
            continue
        if ln.strip().startswith("<"):
            flush()
            out.append(ln)
            i += 1
            continue
        if not ln.strip():
            flush()
            i += 1
            continue
        para.append(ln.strip())
        i += 1
    flush()
    # contents: h2 entries with nested h3
    t, open_sub = ["<ol>"], False
    for lvl, hid, text in toc:
        if lvl == 2:
            if open_sub:
                t.append("</ol></li>")
                open_sub = False
            elif len(t) > 1:
                t.append("</li>")
            t.append('<li><a href="#%s">%s</a>' % (hid, text))
        else:
            if not open_sub:
                t.append("<ol>")
                open_sub = True
            t.append('<li><a href="#%s">%s</a></li>' % (hid, text))
    t.append("</ol></li></ol>" if open_sub else ("</li></ol>" if len(t) > 1 else "</ol>"))
    return "\n".join(out), "".join(t)


def inject_docs(page):
    for key, fname, prefix in (("GUIDE", "user-guide.md", "guide"), ("METHODS", "model.md", "methods")):
        body, toc = render_markdown(read(os.path.join(ROOT, "docs", fname)), prefix)
        page = re.sub(r"<!-- BUILD:%s -->.*?<!-- /BUILD:%s -->" % (key, key), lambda m: body, page, flags=re.S)
        page = re.sub(r"<!-- BUILD:%s_TOC -->.*?<!-- /BUILD:%s_TOC -->" % (key, key), lambda m: toc, page, flags=re.S)
    return page


def main():
    # sync data into web/data for the multi-file source version
    wd = os.path.join(WEB, 'data')
    os.makedirs(wd, exist_ok=True)
    for f in os.listdir(DATA):
        if f.endswith('.json'):
            shutil.copy2(os.path.join(DATA, f), os.path.join(wd, f))
    html = read(os.path.join(WEB, 'index.html'))
    css = read(os.path.join(WEB, 'css', 'app.css'))
    js = read(os.path.join(WEB, 'js', 'dsa-engine.js')) + '\n' + read(os.path.join(WEB, 'js', 'app.js'))
    html = inject_docs(html)
    html = re.sub(r'<!-- BUILD:CSS -->.*?<!-- /BUILD:CSS -->', lambda m: '<style>\n' + css + '\n</style>', html, flags=re.S)
    html = re.sub(r'<!-- BUILD:JS -->.*?<!-- /BUILD:JS -->', lambda m: '<script>\n' + js.replace('</script', '<\\/script') + '\n</script>', html, flags=re.S)
    for target in ('site', 'artifact'):
        out = os.path.join(DIST, target)
        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        shutil.copytree(os.path.join(WEB, 'img'), os.path.join(out, 'img'))
        shutil.copytree(wd, os.path.join(out, 'data'))
        page = html
        if target == 'artifact':
            head = re.search(r'<head>(.*?)</head>', page, re.S).group(1)
            body = re.search(r'<body>(.*?)</body>', page, re.S).group(1)
            head = re.sub(r'<meta charset[^>]*>\s*|<meta name="viewport"[^>]*>\s*', '', head)
            page = head.strip() + '\n' + body.strip() + '\n'
        with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(page)
        size = sum(os.path.getsize(os.path.join(d, x)) for d, _, fs in os.walk(out) for x in fs)
        print('%-9s %s  (%.1f MB total)' % (target, os.path.join(out, 'index.html'), size / 1e6))


if __name__ == '__main__':
    main()
