"""UI 4.0 皮肤注入（纯 CSS 覆盖层，不改 DOM/JS）。

- 把 assets/v4.css 复制进 work/assets/ui/
- 在 index.html 的 styles.css 之后追加 <link rel="stylesheet" href="v4.css">
设计计划见 UI-4.0-DESIGN.md。回退 = 不调用本模块。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINK = '<link rel="stylesheet" href="v4.css">'


def apply(work):
    work = Path(work)
    ui = work / 'assets/ui'
    for name in ('v4.css', 'v4-platinum.css', 'skin.js'):
        (ui / name).write_text((HERE / 'assets' / name).read_text(encoding='utf-8'), encoding='utf-8')

    html = (ui / 'index.html').read_text(encoding='utf-8')
    assert 'href="v4.css"' not in html, 'v4 已注入'
    anchor = '<link rel="stylesheet" href="styles.css">'
    assert html.count(anchor) == 1, 'styles.css link 变了'
    html = html.replace(anchor, chr(10).join([anchor, LINK,
                                        '<link rel="stylesheet" href="v4-platinum.css">',
                                        '<script src="skin.js"></script>']), 1)
    card = (HERE / 'assets/skin_card.html').read_text(encoding='utf-8')
    page = '<section class="page" id="page-settings">'
    assert page in html and 'id="cardSkin"' not in html
    html = html.replace(page, page + chr(10) + card, 1)
    (ui / 'index.html').write_text(html, encoding='utf-8')
