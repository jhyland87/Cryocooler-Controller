"""Minimal KiCad s-expression parser/serializer and symbol-library helpers."""
import re
from pathlib import Path

STOCK_SYMBOLS = Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols')
TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text):
    """Parses s-expression text into nested lists. Quoted strings keep their quotes as ('s', value)."""
    stack = [[]]
    for tok in TOKEN.findall(text):
        if tok == '(':
            stack.append([])
        elif tok == ')':
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(('s', tok[1:-1]))
        else:
            stack[-1].append(tok)
    return stack[0][0]


def dump(node, indent=0):
    """Serializes a parsed node back to KiCad-style text."""
    if isinstance(node, tuple):
        return '"' + node[1] + '"'
    if isinstance(node, str):
        return node
    inline = '(' + ' '.join(dump(c) for c in node) + ')'
    if len(inline) < 100 and not any(isinstance(c, list) and c and c[0] in ('symbol', 'pin') for c in node):
        return inline
    pad = '\t' * (indent + 1)
    head = []
    rest = []
    for c in node:
        (rest if isinstance(c, list) else head if not rest else rest).append(c)
    out = '(' + ' '.join(dump(c) for c in head)
    for c in rest:
        out += '\n' + pad + dump(c, indent + 1)
    return out + '\n' + '\t' * indent + ')'


def sval(node):
    return node[1] if isinstance(node, tuple) else node


def find_all(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def load_library(path):
    """Returns {symbol_name: node} for top-level symbols of a .kicad_sym file."""
    root = parse(Path(path).read_text())
    return {sval(c[1]): c for c in root if isinstance(c, list) and c and c[0] == 'symbol'}


_cache = {}


def stock_symbol(lib, name):
    """Loads a symbol from a stock library, resolving 'extends' into a flat symbol."""
    if lib not in _cache:
        _cache[lib] = load_library(STOCK_SYMBOLS / f'{lib}.kicad_sym')
    return resolve(_cache[lib], name)


def resolve(library, name):
    """Flattens a symbol that 'extends' another: base graphics/pins plus derived properties."""
    node = library[name]
    ext = find_all(node, 'extends')
    if not ext:
        return node
    base = resolve(library, sval(ext[0][1]))
    base_name = sval(base[1])
    props = {sval(p[1]): p for p in find_all(node, 'property')}
    base_props = {sval(c[1]) for c in base[2:] if isinstance(c, list) and c and c[0] == 'property'}
    out = ['symbol', ('s', name)]
    extras_added = False
    for c in base[2:]:
        is_node = isinstance(c, list) and c
        if is_node and c[0] == 'property' and sval(c[1]) in props:
            out.append(props[sval(c[1])])
        elif is_node and c[0] == 'symbol':
            if not extras_added:
                out.extend(p for key, p in props.items() if key not in base_props)
                extras_added = True
            sub = list(c)
            sub[1] = ('s', sval(c[1]).replace(base_name, name, 1))
            out.append(sub)
        else:
            out.append(c)
    return out


def pins(symbol):
    """Yields (number, name, x, y, angle, length, type) for every pin in a symbol node."""
    result = []

    def walk(n):
        for c in n:
            if isinstance(c, list) and c:
                if c[0] == 'pin':
                    at = find_all(c, 'at')[0]
                    ln = find_all(c, 'length')[0]
                    number = sval(find_all(c, 'number')[0][1])
                    pname = sval(find_all(c, 'name')[0][1])
                    result.append((number, pname, float(at[1]), float(at[2]), float(at[3]), float(ln[1]), c[1]))
                elif c[0] == 'symbol':
                    walk(c)
    walk(symbol)
    return result
