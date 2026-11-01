"""
@file drawio.py
@brief Tiny builder for uncompressed draw.io (mxGraphModel) files.

Each figure is built with a Diagram: add nodes (boxes, circles, triangles,
text), edges between them, free polylines (boundaries) and notes, then save().
Coordinates are draw.io pixels. Reference numerals from the patents are shown
as a small grey second line in the node label.
"""

import html
import xml.etree.ElementTree as ET

# ─── Shape styles ───
SHAPES = {
    'box': 'rounded=0;whiteSpace=wrap;html=1;',
    'rbox': 'rounded=1;whiteSpace=wrap;html=1;',
    'circle': 'ellipse;whiteSpace=wrap;html=1;aspect=fixed;',
    'ellipse': 'ellipse;whiteSpace=wrap;html=1;',
    'tri': 'triangle;whiteSpace=wrap;html=1;',
    'tri_left': 'triangle;whiteSpace=wrap;html=1;direction=west;',
    'adc': 'shape=offPageConnector;whiteSpace=wrap;html=1;direction=east;rotation=-90;',
    'pentagon': 'shape=step;perimeter=stepPerimeter;whiteSpace=wrap;html=1;fixedSize=1;size=14;',
    'trap': 'shape=trapezoid;perimeter=trapezoidPerimeter;whiteSpace=wrap;html=1;direction=south;',
    'diamond': 'rhombus;whiteSpace=wrap;html=1;',
    'text': 'text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;strokeColor=none;fillColor=none;',
    'ltext': 'text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;strokeColor=none;fillColor=none;',
    'dot': 'ellipse;html=1;aspect=fixed;fillColor=#000000;strokeColor=#000000;',
    'group': 'rounded=0;whiteSpace=wrap;html=1;dashed=1;fillColor=none;verticalAlign=top;align=left;spacingLeft=6;',
    'note': 'shape=note;whiteSpace=wrap;html=1;size=12;align=left;verticalAlign=top;spacingLeft=6;fillColor=#fff2cc;strokeColor=#d6b656;',
    'state': 'rounded=1;whiteSpace=wrap;html=1;arcSize=20;',
    'start': 'ellipse;html=1;aspect=fixed;fillColor=#000000;',
}

EDGE = 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;'


def label_html(text, ref=None):
    """Return an HTML label: text lines plus an optional grey reference numeral."""
    body = '<br>'.join(html.escape(line) for line in text.split('\n'))
    if ref:
        body += f'<br><font style="font-size:9px" color="#808080">{html.escape(str(ref))}</font>'
    return body


class Diagram:
    """One draw.io page."""

    def __init__(self, name, title, source):
        self.name = name
        self.cells = []
        self.ids = set()
        self.edges = []
        self.counter = 0
        self.text('title', f'<b>{html.escape(title)}</b><br><i>{html.escape(source)}</i>',
                  10, -70, 900, 40, raw=True, shape='ltext')

    def _id(self, wanted=None):
        if wanted:
            assert wanted not in self.ids, f'duplicate id {wanted}'
            self.ids.add(wanted)
            return wanted
        self.counter += 1
        while f'e{self.counter}' in self.ids:
            self.counter += 1
        self.ids.add(f'e{self.counter}')
        return f'e{self.counter}'

    def node(self, node_id, text, x, y, w=110, h=50, shape='box', ref=None, style=''):
        """Add a vertex. `text` uses \\n for line breaks."""
        self._id(node_id)
        self.cells.append(('v', node_id, label_html(text, ref), SHAPES[shape] + style, x, y, w, h))
        return node_id

    def text(self, node_id, text, x, y, w=120, h=30, raw=False, shape='text', style=''):
        """Add a free text vertex (also usable as an edge endpoint)."""
        self._id(node_id)
        value = text if raw else label_html(text)
        self.cells.append(('v', node_id, value, SHAPES[shape] + style, x, y, w, h))
        return node_id

    def dot(self, node_id, x, y):
        """Add a small junction dot centred on (x, y)."""
        return self.node(node_id, '', x - 4, y - 4, 8, 8, shape='dot')

    def edge(self, src, dst, label='', points=(), style='', exit_=None, entry=None):
        """Connect two vertices; exit_/entry are (x, y) fractions of the node box."""
        edge_id = self._id()
        extra = ''
        if exit_:
            extra += f'exitX={exit_[0]};exitY={exit_[1]};exitDx=0;exitDy=0;'
        if entry:
            extra += f'entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;'
        self.edges.append((edge_id, src, dst))
        self.cells.append(('e', edge_id, label_html(label) if label else '', EDGE + extra + style,
                           src, dst, list(points)))
        return edge_id

    def line(self, points, style='', label=''):
        """Free polyline with no endpoints (boundaries, dashed links)."""
        edge_id = self._id()
        self.cells.append(('l', edge_id, label_html(label) if label else '',
                           'endArrow=none;html=1;rounded=0;' + style, list(points)))
        return edge_id

    def to_xml(self):
        """Serialise as an mxGraphModel element."""
        model = ET.Element('mxGraphModel', dx='1200', dy='800', grid='1', gridSize='10',
                           guides='1', tooltips='1', connect='1', arrows='1', fold='1',
                           page='1', pageScale='1', pageWidth='1169', pageHeight='827',
                           math='0', shadow='0')
        root = ET.SubElement(model, 'root')
        ET.SubElement(root, 'mxCell', id='0')
        ET.SubElement(root, 'mxCell', id='1', parent='0')
        for cell in self.cells:
            kind = cell[0]
            if kind == 'v':
                _, cid, value, style, x, y, w, h = cell
                c = ET.SubElement(root, 'mxCell', id=cid, value=value, style=style,
                                  vertex='1', parent='1')
                ET.SubElement(c, 'mxGeometry', x=str(x), y=str(y), width=str(w),
                              height=str(h), **{'as': 'geometry'})
            elif kind == 'e':
                _, cid, value, style, src, dst, pts = cell
                c = ET.SubElement(root, 'mxCell', id=cid, value=value, style=style, edge='1',
                                  parent='1', source=src, target=dst)
                g = ET.SubElement(c, 'mxGeometry', relative='1', **{'as': 'geometry'})
                if pts:
                    arr = ET.SubElement(g, 'Array', **{'as': 'points'})
                    for px, py in pts:
                        ET.SubElement(arr, 'mxPoint', x=str(px), y=str(py))
            else:
                _, cid, value, style, pts = cell
                c = ET.SubElement(root, 'mxCell', id=cid, value=value, style=style, edge='1',
                                  parent='1')
                g = ET.SubElement(c, 'mxGeometry', relative='1', **{'as': 'geometry'})
                ET.SubElement(g, 'mxPoint', x=str(pts[0][0]), y=str(pts[0][1]),
                              **{'as': 'sourcePoint'})
                ET.SubElement(g, 'mxPoint', x=str(pts[-1][0]), y=str(pts[-1][1]),
                              **{'as': 'targetPoint'})
                if len(pts) > 2:
                    arr = ET.SubElement(g, 'Array', **{'as': 'points'})
                    for px, py in pts[1:-1]:
                        ET.SubElement(arr, 'mxPoint', x=str(px), y=str(py))
        return model

    def check(self):
        """Every edge must reference existing vertices."""
        vertices = {c[1] for c in self.cells if c[0] == 'v'}
        for edge_id, src, dst in self.edges:
            assert src in vertices and dst in vertices, f'{self.name}: orphan edge {edge_id}'


def save(path, diagrams):
    """Write one .drawio file holding one page per Diagram."""
    mxfile = ET.Element('mxfile', host='app.diagrams.net', type='device')
    for index, diagram in enumerate(diagrams):
        diagram.check()
        page = ET.SubElement(mxfile, 'diagram', id=f'page{index}', name=diagram.name)
        page.append(diagram.to_xml())
    ET.indent(mxfile)
    ET.ElementTree(mxfile).write(path, encoding='utf-8', xml_declaration=True)
