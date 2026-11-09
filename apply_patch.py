"""Add optional Friendship Points purchases, tracking, icon and DB history.
Run from anywhere: python apply_patch.py PATH_TO_E7AUTOSHOP
"""
from pathlib import Path
import sys, re, shutil, xml.etree.ElementTree as ET
import struct, zlib

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
for file in ('main.py','models.py','scripts/shop.py','main.ui','resource.qrc'):
    if not (root / file).is_file():
        raise SystemExit(f'Cannot find {file} in {root}; pass the repository directory.')


def change(filename, func):
    p = root / filename
    original = p.read_text(encoding='utf-8')
    changed = func(original)
    if changed == original:
        raise ValueError(f'{filename}: patch made no changes; repo version may differ or already patched')
    shutil.copy2(p, p.with_suffix(p.suffix+'.friendship-backup'))
    p.write_text(changed, encoding='utf-8')
    print('Updated', filename)


def replace_once(text, old, new):
    count = text.count(old)
    if count != 1:
        raise ValueError(f'Expected 1 occurrence, found {count}: {old[:95]!r}')
    return text.replace(old, new, 1)


def patch_shop(s):
    s=replace_once(s, 'def __init__(self, skystones) -> None:', 'def __init__(self, skystones, buy_friendships=True) -> None:')
    s=replace_once(s, '        self.skystones = skystones', '        self.skystones = skystones\n        self.buy_friendships = buy_friendships')
    s=replace_once(s, '        autoshop = Shop()', '        autoshop = Shop(buy_friendships=self.buy_friendships)')
    s=replace_once(s, "    inventory = {\n        'covenants': 0,\n        'mystics': 0,", "    inventory = {\n        'covenants': 0,\n        'mystics': 0,\n        'friendships': 0,")
    s=replace_once(s, '    def __init__(self) -> None:', '    def __init__(self, buy_friendships=True) -> None:')
    s=replace_once(s, "        self.purchase_list = ['184000', '280000']", "        self.purchase_list = ['184000', '280000']\n        if buy_friendships:\n            self.purchase_list.append('18000')")
    # The game replaced its 5 Friendship Bookmarks with 50 Friendship Points in Feb 2026.
    s=replace_once(s, "return 'Friendship Bookmarks'", "return 'Friendship Points'")
    s=replace_once(s, "self.inventory['friendships']+= 5", "self.inventory['friendships']+= 50")
    s=replace_once(s, "self.output.append(f'Purchased: Friendship Bookmarks')", "self.output.append(f'Purchased: 50 Friendship Points')")
    # Make sure reset clears friendship quantities too (the dictionary is cumulative).
    s=replace_once(s, "    def clear_inventory(self):\n        self.inventory.update({\n        'covenants': 0,\n        'mystics': 0,", "    def clear_inventory(self):\n        self.inventory.update({\n        'covenants': 0,\n        'mystics': 0,\n        'friendships': 0,")
    return s


def patch_models(s):
    s=replace_once(s, 'from datetime import datetime, timedelta', 'from datetime import datetime, timedelta\nimport sqlite3')
    s=replace_once(s, 'class Sessions(SQLObject):', '''# Migrate existing users' databases without discarding their purchase history.
# SQLObject's createTable(ifNotExists=True) does not add new columns.
with sqlite3.connect(database_file) as _db:
    _existing = _db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()
    if _existing:
        _columns = {row[1] for row in _db.execute('PRAGMA table_info(sessions)')}
        if 'friendships' not in _columns:
            _db.execute('ALTER TABLE sessions ADD COLUMN friendships INTEGER NOT NULL DEFAULT 0')

class Sessions(SQLObject):''')
    s=replace_once(s, '    mystics = IntCol()', '    mystics = IntCol()\n    friendships = IntCol(default=0)')
    s=replace_once(s, 'def create_update(cls, date, covenants, mystics, gems, gold):', 'def create_update(cls, date, covenants, mystics, gems, gold, friendships=0):')
    s=replace_once(s, 'cls(date=date, covenants=covenants, mystics=mystics, gems_spent=gems, gold_spent=gold)', 'cls(date=date, covenants=covenants, mystics=mystics, gems_spent=gems, gold_spent=gold, friendships=friendships)')
    s=replace_once(s, '            entry.mystics += mystics', '            entry.mystics += mystics\n            entry.friendships += friendships')
    return s


def patch_main(s):
    s=replace_once(s, '        header.setSectionResizeMode(4, QHeaderView.Stretch)', '        header.setSectionResizeMode(4, QHeaderView.Stretch)\n        header.setSectionResizeMode(5, QHeaderView.Stretch)')
    s=replace_once(s, 'self.shop_thread = ShopThread(refreshes)', 'self.shop_thread = ShopThread(refreshes, buy_friendships=self.ui.buy_friendships_checkbox.isChecked())')
    s=replace_once(s, '        self.currency(0, 0, 0, 0)   # reset currency and colors', '        self.currency(0, 0, 0, 0, 0)   # reset currency and colors')
    s=replace_once(s, 'gold=stash["gold_spent"])', 'gold=stash["gold_spent"], friendships=stash.get("friendships", 0))')
    s=replace_once(s, 'def currency(self, cov: int, myst: int, sky: int, gold: int):', 'def currency(self, cov: int, myst: int, sky: int, gold: int, friendships: int = 0):')
    s=replace_once(s, '        self.ui.mystic_label.setText(str(myst))', '        self.ui.mystic_label.setText(str(myst))\n        self.ui.friendship_label.setText(str(friendships))')
    s=replace_once(s, '        self.ui.mystic_label.setStyleSheet(f"color: {color};")', '        self.ui.mystic_label.setStyleSheet(f"color: {color};")\n        self.ui.friendship_label.setStyleSheet(f"color: {color};")')
    s=replace_once(s, "            'mystics': (self.ui.mystic_label, 'green'),", "            'mystics': (self.ui.mystic_label, 'green'),\n            'friendships': (self.ui.friendship_label, 'green'),")
    s=replace_once(s, "self.currency(inventory['covenants'], inventory['mystics'], inventory['gems_spent'], inventory['gold_spent'])", "self.currency(inventory['covenants'], inventory['mystics'], inventory['gems_spent'], inventory['gold_spent'], inventory.get('friendships', 0))")
    s=replace_once(s, "            for key, (label, color) in inventory_styles.items():\n                if inventory[key] > 0:", "            for key, (label, color) in inventory_styles.items():\n                if inventory.get(key, 0) > 0:")
    s=replace_once(s, 'self.ui.tableWidget.setItem(index, 4, QTableWidgetItem(str(row.gold_spent)))', 'self.ui.tableWidget.setItem(index, 4, QTableWidgetItem(str(row.gold_spent)))\n            self.ui.tableWidget.setItem(index, 5, QTableWidgetItem(str(row.friendships)))')
    return s


def prop(widget, name, tag, value):
    p=ET.SubElement(widget,'property',{'name':name})
    ET.SubElement(p,tag).text=value


def label_item(name, pixmap=None):
    item=ET.Element('item')
    w=ET.SubElement(item,'widget',{'class':'QLabel','name':name})
    prop(w,'toolTip','string','Friendship Points purchased')
    if pixmap:
        prop(w,'text','string','')
        p=ET.SubElement(w,'property',{'name':'pixmap'})
        ET.SubElement(p,'pixmap',{'resource':'resource.qrc'}).text=':/images/img/friendship.png'
        p=ET.SubElement(w,'property',{'name':'maximumSize'})
        sz=ET.SubElement(p,'size')
        ET.SubElement(sz,'width').text='40'
        ET.SubElement(sz,'height').text='40'
    else:
        prop(w,'text','string','0')
    return item


def patch_ui(s):
    doc=ET.fromstring(s)
    layout=doc.find(".//layout[@name='horizontalLayout_9']")
    assert layout is not None
    layout.append(label_item('friendship_icon',True))
    layout.append(label_item('friendship_label'))
    # Keep checkbox visible on the main shop screen, with purchasing enabled by default.
    controls=doc.find(".//layout[@name='verticalLayout']")
    assert controls is not None
    item=ET.Element('item')
    cb=ET.SubElement(item,'widget',{'class':'QCheckBox','name':'buy_friendships_checkbox'})
    prop(cb,'text','string','Buy Friendship Points (18,000 gold)')
    prop(cb,'checked','bool','true')
    controls.insert(0,item)
    table=doc.find(".//widget[@name='tableWidget']")
    assert table is not None
    column=ET.SubElement(table,'column')
    prop(column,'text','string','Friendship')
    ET.indent(doc,space=' ')
    return '<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(doc,encoding='unicode')+'\n'


def patch_qrc(s):
    return replace_once(s, '    <file>img/cov.png</file>', '    <file>img/cov.png</file>\n    <file>img/friendship.png</file>')


def create_icon(path):
    # Self-contained PNG generator: gold coin with pink handshake-like paired hearts.
    W=H=40
    rows=[]
    for y in range(H):
        line=bytearray([0])
        for x in range(W):
            dx=x-19.5;dy=y-19.5; r=(dx*dx+dy*dy)**0.5
            rgba=(0,0,0,0)
            if r<18: rgba=(164,94,18,255)
            if r<16: rgba=(249,194,65,255)
            if r<13.5: rgba=(255,225,120,255)
            # overlapping hearts distinguish friendship from the bookmarks icons
            heart1=((x-14)**2+(y-16)**2<30 or (x-21)**2+(y-16)**2<30 or (abs(x-17.5)<(31-y)*0.75 and 17<=y<=30))
            if heart1 and 11<=x<=28 and 11<=y<=30: rgba=(211,70,119,255)
            if 18<=x<=29 and 14<=y<=24 and (x-24)**2+(y-18)**2<35: rgba=(253,137,163,255)
            line.extend(rgba)
        rows.append(bytes(line))
    raw=zlib.compress(b''.join(rows),9)
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,6,0,0,0))+chunk(b'IDAT',raw)+chunk(b'IEND',b''))


if __name__=='__main__':
    # Stop early on a previously patched repo, instead of creating duplicate UI columns.
    if 'friendship_label' in (root/'main.ui').read_text(encoding='utf-8'):
        raise SystemExit('This repo appears to have the Friendship patch already.')
    # Check modifications before writing so a different upstream version does not half-patch.
    transforms={'scripts/shop.py':patch_shop,'models.py':patch_models,'main.py':patch_main,'main.ui':patch_ui,'resource.qrc':patch_qrc}
    prepared={name:fn((root/name).read_text(encoding='utf-8')) for name,fn in transforms.items()}
    for name,content in prepared.items():
        p=root/name
        shutil.copy2(p,p.with_suffix(p.suffix+'.friendship-backup'))
        p.write_text(content,encoding='utf-8')
        print('Updated',name)
    create_icon(root/'img'/'friendship.png')
    print('Created img/friendship.png')
    print('Regenerate UI/resources: pyuic5 -x main.ui -o ui.py && pyrcc5 resource.qrc -o resource_rc.py')
