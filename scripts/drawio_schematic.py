"""Editable monochrome RTL schematics using the draw.io XML format.

All generated connectors reference explicit port vertices. Geometry checks are
conservative bounding-box checks; exported visual review is still required.
"""
import base64
import urllib.parse
import xml.etree.ElementTree as E
import zlib

FILE = E.Element('mxfile', host='Electron', agent='draw.io', version='31.7.0', type='device')
BASE = 'html=0;whiteSpace=wrap;fontFamily=serif;fontSize=18;fontColor=#000000;strokeColor=#000000;fillColor=#ffffff;strokeWidth=1.4;rounded=0;shadow=0;'

def stencil(path):
    xml = '<shape name="symbol" w="100" h="100" aspect="variable" strokewidth="inherit"><foreground><path>' + path + '</path><fillstroke/></foreground></shape>'
    encoded = urllib.parse.quote(xml, safe="~()*!.'-")
    obj = zlib.compressobj(wbits=-15)
    return 'stencil(' + base64.b64encode(obj.compress(encoded.encode()) + obj.flush()).decode() + ')'

MUX = stencil('<move x="0" y="0"/><line x="100" y="12"/><line x="100" y="88"/><line x="0" y="100"/><close/>')
PORT = stencil('<move x="0" y="10"/><line x="70" y="10"/><line x="100" y="50"/><line x="70" y="90"/><line x="0" y="90"/><close/>')

class Page:
    def __init__(self, ident, name, w, h):
        self.id = ident
        dia = E.SubElement(FILE, 'diagram', id=ident, name=name)
        self.model = E.SubElement(dia, 'mxGraphModel', dx='0', dy='0', grid='1', gridSize='10', guides='1', tooltips='1', connect='1', arrows='1', fold='1', page='1', pageScale='1', pageWidth=str(w), pageHeight=str(h), math='0', shadow='0', background='#ffffff')
        self.root = E.SubElement(self.model, 'root')
        E.SubElement(self.root, 'mxCell', id='0')
        E.SubElement(self.root, 'mxCell', id='1', parent='0')
        self.n = 0
        self.rects = {}
        self.pins = {}
        self.edges = []
    def new(self, prefix):
        self.n += 1
        return f'{self.id}_{prefix}_{self.n}'
    def vertex(self, name, x, y, w, h, style='', obstacle=True, ident=None, parent='1'):
        ident = ident or self.new('v')
        cell = E.SubElement(self.root, 'mxCell', id=ident, value=name, style=BASE+style, vertex='1', parent=parent)
        E.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), **{'as':'geometry'})
        if obstacle:
            self.rects[ident] = (x,y,w,h)
        return ident
    def label(self, text, x, y, w=180, h=22, size=16, align='center'):
        return self.vertex(text,x,y,w,h,f'text;strokeColor=none;fillColor=none;align={align};verticalAlign=middle;fontSize={size};spacing=0;',False)
    def block(self, name, x,y,w,h):
        return self.vertex(name,x,y,w,h,'align=center;verticalAlign=middle;spacing=12;')
    def reg(self, name,x,y,w,h):
        node=self.block(name,x,y,w,h)
        # A clock-edge triangle is part of the register symbol, not a data net.
        self.vertex('',0,h-28,10,16,'shape=triangle;direction=east;strokeWidth=1;fillColor=none;',False,parent=node)
        self.vertex('clk',12,h-28,35,16,'text;strokeColor=none;fillColor=none;fontSize=12;align=left;spacing=0;',False,parent=node)
        return node
    def fifo(self,name,x,y,w,h):
        node=self.block(name,x,y,w,h)
        self.vertex('',7,7,w-14,4,'shape=line;strokeWidth=1;',False,parent=node)
        self.vertex('',7,h-11,w-14,4,'shape=line;strokeWidth=1;',False,parent=node)
        return node
    def mux(self,name,x,y,w,h):
        return self.vertex(name,x,y,w,h,'shape='+MUX+';align=center;verticalAlign=middle;fontSize=16;')
    def pin(self,node,x,y,name='',side='L'):
        ident=self.new('pin')
        bx,by,bw,bh=self.rects[node]
        cell=E.SubElement(self.root,'mxCell',id=ident,value='',style=BASE+'resizable=0;movable=0;portConstraint=eastwest;',vertex='1',parent=node)
        E.SubElement(cell,'mxGeometry',x=str(x-bx-2.5),y=str(y-by-2.5),width='5',height='5',**{'as':'geometry'})
        self.pins[ident]=(x,y,node)
        if name:
            ox=8 if side=='L' else -68
            self.vertex(name,x-bx+ox,y-by-9,60,18,'text;strokeColor=none;fillColor=none;fontSize=12;align='+('left' if side=='L' else 'right')+';spacing=0;',False,parent=node)
        return ident
    def terminal(self,name,x,y,output=False,width=170,above=False):
        node=self.vertex('',x-10,y-6,20,12,'shape='+PORT+';',False)
        self.pins[node]=(x,y,None)
        if above:
            self.label(name,x-width/2,y-30,width,20,14)
        elif output:
            self.label(name,x+16,y-11,width,22,14,'left')
        else:
            self.label(name,x-width-16,y-11,width,22,14,'right')
        return node
    def edge(self,a,b,via=(),label=None,lpos=None,bus=False,arrow=True):
        ident=self.new('e')
        style='edgeStyle=none;rounded=0;html=0;strokeColor=#000000;strokeWidth='+('1.7' if bus else '1.2')+';endArrow='+('open' if arrow else 'none')+';endFill=0;endSize=6;startArrow=none;exitX=0.5;exitY=0.5;exitPerimeter=0;entryX=0.5;entryY=0.5;entryPerimeter=0;jumpStyle=arc;jumpSize=6;'
        cell=E.SubElement(self.root,'mxCell',id=ident,value='',style=style,edge='1',parent='1',source=a,target=b)
        geom=E.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
        if via:
            pts=E.SubElement(geom,'Array',**{'as':'points'})
            for x,y in via:E.SubElement(pts,'mxPoint',x=str(x),y=str(y))
        self.edges.append((ident,a,b,[self.pins[a][:2],*via,self.pins[b][:2]]))
        if label:
            x,y,w=lpos
            self.label(label,x,y,w,20,13)
        return ident
    def input(self,node,x,y,name,width=190,span=120):
        a=self.terminal(name,x-span,y,width=width,above=True)
        b=self.pin(node,x,y)
        self.edge(a,b)
        return b
    def output(self,node,x,y,name,width=190,span=90):
        a=self.pin(node,x,y,side='R')
        b=self.terminal(name,x+span,y,True,width)
        self.edge(a,b)
        return a
    def check(self):
        issues=[]
        for cell in self.root:
            if cell.get('parent')!='1' or 'text;' not in cell.get('style',''):
                continue
            g=cell.find('mxGeometry')
            if g is None:continue
            lx,ly,lw,lh=[float(g.get(k,0)) for k in ['x','y','width','height']]
            for node,(x,y,w,h) in self.rects.items():
                overlap=max(lx,x)<min(lx+lw,x+w) and max(ly,y)<min(ly+lh,y+h)
                inside=lx>=x and ly>=y and lx+lw<=x+w and ly+lh<=y+h
                if overlap and not inside:
                    issues.append([cell.get('value'),'label crosses block',node])
        for eid,a,b,pts in self.edges:
            own={self.pins[a][2],self.pins[b][2]}
            for (x1,y1),(x2,y2) in zip(pts,pts[1:]):
                if x1!=x2 and y1!=y2:issues.append([eid,'non-orthogonal',[x1,y1,x2,y2]])
                for node,(x,y,w,h) in self.rects.items():
                    if node in own:continue
                    if x1==x2 and x+1<x1<x+w-1 and max(min(y1,y2),y+1)<min(max(y1,y2),y+h-1):issues.append([eid,'wire crosses block',node])
                    if y1==y2 and y+1<y1<y+h-1 and max(min(x1,x2),x+1)<min(max(x1,x2),x+w-1):issues.append([eid,'wire crosses block',node])
        return issues


def save_document(path):
    """Save the current document without normalizing newlines in XML values."""
    E.ElementTree(FILE).write(str(path), encoding='utf-8', xml_declaration=True)

def connect(page, source, target, sy=None, ty=None, via=(), label=None, lpos=None):
    """Connect the right face of source to the left face of target."""
    x,y,w,h=page.rects[source]
    tx,yy,tw,th=page.rects[target]
    sy=y+h/2 if sy is None else sy
    ty=yy+th/2 if ty is None else ty
    a=page.pin(source,x+w,sy,side='R')
    b=page.pin(target,tx,ty)
    if sy!=ty and not via:
        mid=(x+w+tx)/2
        via=[(mid,sy),(mid,ty)]
    return page.edge(a,b,via,label,lpos,bus=True)
