#
# Copyright (c) 2006,2007 Jonathan Harris
# 
# Mail: <x-plane@marginal.org.uk>
# Web:  http://marginal.org.uk/x-planescenery/
#
# See FS2XPlane.html for usage.
#
# This software is licensed under a Creative Commons License
#   Attribution-ShareAlike 2.5:
#
#   You are free:
#     * to copy, distribute, display, and perform the work
#     * to make derivative works
#     * to make commercial use of the work
#   Under the following conditions:
#     * Attribution: You must give the original author credit.
#     * Share Alike: If you alter, transform, or build upon this work, you
#       may distribute the resulting work only under a license identical to
#       this one.
#   For any reuse or distribution, you must make clear to others the license
#   terms of this work.
#
# This is a human-readable summary of the Legal Code (the full license):
#   http://creativecommons.org/licenses/by-sa/2.5/legalcode
#

from math import sin, cos, pi, radians, degrees
from os.path import join
from sys import maxint

from OpenGL.GL import GL_LINE_LOOP, GL_TRUE
from OpenGL.GLU import *
try:
    # apparently older PyOpenGL version didn't define gluTessVertex
    gluTessVertex
except NameError:
    from OpenGL import GLU
    gluTessVertex = GLU._gluTessVertex

from convutil import AptNav, Point

twopi=pi+pi

# Runway, taxiway & helipad surfaces
surfaces={'ASPHALT':1, 'BITUMINOUS':1, 'MACADAM':1,
          'OIL_TREATED':1, 'TARMAC':1, 
          'BRICK':2, 'CEMENT':2, 'CONCRETE':2, 'STEEL_MATS':2,
          'GRASS':3,
          'DIRT':4, 'PLANKS':4, 'UNKNOWN':4,
          'SHALE':5, 'CORAL':5, 'GRAVEL':5,
          'CLAY':12, 'SAND':12,
          'WATER':13,
          'ICE':14, 'SNOW':14,}

designators={'C':'C', 'CENTER':'C', 'L':'L', 'LEFT':'L', 'R':'R', 'RIGHT':'R'}

# member var is defined
def D(c, v):
    return (v in dir(c) and eval("c.%s" % v))

# member var is defined and true
def T(c, v):
    return (v in dir(c) and eval("c.%s" % v)=='TRUE')

class Node:
    parking={'E_PARKING':'East ',  'NE_PARKING':'North East ',
             'N_PARKING':'North ', 'NW_PARKING':'North West ',
             'SE_PARKING':'South East ', 'S_PARKING':'South ',
             'SW_PARKING':'South West ', 'W_PARKING':'West ',
             'PARKING':''}
    types={'RAMP_CARGO':'Cargo ',
           'RAMP_GA':'GA ',        'RAMP_GA_LARGE':'GA ',
           'RAMP_GA_MEDIUM':'GA ', 'RAMP_GA_SMALL':'GA ',
           'RAMP_MIL_CARGO':'Mil cargo ', 'RAMP_MIL_COMBAT':'Military '}
    gates=['GATE_A', 'GATE_B', 'GATE_C', 'GATE_D', 'GATE_E', 'GATE_F',
           'GATE_G', 'GATE_H', 'GATE_I', 'GATE_J', 'GATE_K', 'GATE_L',
           'GATE_M', 'GATE_N', 'GATE_O', 'GATE_P', 'GATE_Q', 'GATE_R',
           'GATE_S', 'GATE_T', 'GATE_U', 'GATE_V', 'GATE_W', 'GATE_X',
           'GATE_Y', 'GATE_Z']

    def __init__(self, point):
        self.type=point.type
        if D(point, 'orientation') and point.orientation=='REVERSE':
            self.reverse=True
        else:
            self.reverse=False
        self.loc=Point(float(point.lat), float(point.lon))
        self.links=[]
        self.donecross=[[]]
        if D(point, 'name'):	# TaxiwayParking
            self.parking=True
        else:
            self.parking=False
        
        if self.parking and self.type not in ['VEHICLE','FUEL']:
            # Plane parking spot
            self.heading=float(point.heading)
            
            # type appears to be secondary to name
            if point.type in Node.gates:
                self.startup='Gate '+point.name[5]
            elif point.name=='GATE':
                self.startup='Gate'
            elif point.name=='DOCK':
                self.startup='Dock'
            elif point.name in Node.parking:
                self.startup=Node.parking[point.name]
                if point.type in Node.types:
                    self.startup+=Node.types[point.type]
                self.startup+='Ramp'
            # No name
            elif point.type.startswith('GATE'):
                self.startup='Gate'
            elif point.type=='DOC_GA':
                self.startup='Dock'
            elif point.type in Node.types:
                self.startup=Node.types[point.type]+'Ramp'
            # wtf
            else:
                self.startup='Ramp'
                
            if int(point.number):
                self.startup="%s %d" % (self.startup, int(point.number))
        else:
            self.startup=None


class Link:	# TaxiwayPath or TaxiwayParking
    def __init__(self, path, parkingoffset, taxinames):
        self.type=path.type
        self.width=float(path.width)
        self.surface=surfaces[path.surface]
        if self.type!='PARKING':
            self.nodes=[int(path.start),int(path.end)]
        else:
            self.nodes=[int(path.start),int(path.end)+parkingoffset]
        if self.type=='RUNWAY':
            # We don't draw anything for runway paths
            self.draw=self.centreline=self.centrelights=False
            self.lines=['NONE','NONE']
            self.lights=[False,False]
            self.name='Runway '+path.number
            if path.designator in designators:
                self.name+=designators[path.designator]
        else:
            if self.type in ['PATH','PARKING']:
                self.draw=False	# No surface for apron paths
            else:
                self.draw=T(path, 'drawSurface') or T(path, 'drawDetail')
            self.centreline=T(path, 'centerLine')
            self.centrelights=T(path, 'centerLineLighted')
            self.lines=[path.rightEdge,path.leftEdge]
            self.lights=[T(path,'rightEdgeLighted'), T(path,'leftEdgeLighted')]
            self.name=self.type[0]+self.type[1:].lower()
            if taxinames[int(path.name)].name:
                self.name+=' '+taxinames[int(path.name)].name
        self.done=0

    def findlinked(self, searchspace, found):
        for n in [self.nodes[0],self.nodes[1]]:
            for link in n.links:
                if link.type=='RUNWAY': break	# stop at runway nodes
            else:
                for link in n.links:
                    if link.surface==self.surface and link in searchspace:
                        searchspace.remove(link)
                        found.append(link)
                        link.findlinked(searchspace, found)


# returns taxiway signs for debugging
def bezpt(out, this, next, ratio, brat, code, deb):
    brat=brat*ratio/3.0
    out.append(AptNav(112, "%10.6f %11.6f %10.6f %11.6f %s" % (
        this.lat+ratio*(next.lat-this.lat), this.lon+ratio*(next.lon-this.lon),
        this.lat+brat *(next.lat-this.lat), this.lon+brat *(next.lon-this.lon),
        code)))
    return [AptNav(20, "%10.6f %11.6f 0 0 5 {@R}%s" % (
        this.lat+ratio*(next.lat-this.lat), this.lon+ratio*(next.lon-this.lon),
        deb)),
            AptNav(20, "%10.6f %11.6f 0 0 5 {@Y}%s" % (
        this.lat+brat *(next.lat-this.lat), this.lon+brat *(next.lon-this.lon),
        deb))]


def edgefeature(link1, end1, link2, end2):
    code=''
    if link1.type!='VEHICLE' and link2.type!='VEHICLE':
        if link1.lines[end1]=='SOLID' or link2.lines[end2]=='SOLID':
            code='53'
        elif link1.lines[end1]=='SOLID_DASHED' or link2.lines[end2]=='SOLID_DASHED':
            code='55'	# ?
        elif link1.lines[end1]=='DASHED' or link2.lines[end2]=='DASHED':
            code='59'
    else:	# vehicle
        if link1.lines[end1]=='SOLID' or link2.lines[end2]=='SOLID':
            code='20'
        elif link1.lines[end1]=='SOLID_DASHED' or link2.lines[end2]=='SOLID_DASHED':
            code='21'	# Use chequerboard
        elif link1.lines[end1]=='DASHED' or link2.lines[end2]=='DASHED':
            code='21'	# Displayed as chequerboard in MSFS
    return code


def follow(subgraph, ccw, allpoints, dump):

    if dump: print "ccw=", ccw, "count=",len(subgraph)

    # Find nodes & links (this is more nodes than a convex hull)
    # start with westmost
    start=subgraph[0].nodes[0]	# a random node
    for link in subgraph:
        for n in [link.nodes[0],link.nodes[1]]:
            if n.loc.lon<start.loc.lon: start=n
    nodes=[start]
    
    # Stop when we get back to first node
    n=nodes[0]
    lastheading=270	# heading to last node
    #if dump: print n.loc, "node", lastheading
    while True:
        # Ack - O(n3) algorithm?!
        bestnode=None
        bestlink=None
        if not ccw and len(nodes)==1:
            bestheading=lastheading+360
        else:
            bestheading=lastheading-360
        #if not n.links: break	# node has no links - ignore
        for link in n.links:
            # find rightmost link
            if not link in subgraph:
                continue	# not this subgraph, or on spur
            for end in [0,1]:
                o=link.nodes[end]
                if o==n:
                    # We have a candidate
                    o=link.nodes[1-end]
                    h=n.loc.headingto(o.loc)
                    if h>=lastheading: h=h-360
                    #if dump: print o.loc, h
                    if not ccw and len(nodes)==1:
                        if h<bestheading:
                            bestnode=o
                            bestlink=link
                            bestheading=h
                    elif h>bestheading:
                        bestnode=o
                        bestlink=link
                        bestheading=h
                    break
        if not bestnode:
            # On a spur - backtrack
            bestnode=nodes[nodes.index(n)-1]
        if len(nodes)>1 and n==nodes[0] and bestnode==nodes[1]:
            # back at start (and not heading in different direction)
            nodes.pop()
            #if dump: print "(stop)"
            break
        nodes.append(bestnode)
        lastheading=bestnode.loc.headingto(n.loc)
        #if dump: print bestnode.loc, "node", lastheading
        n=bestnode

    #if len(nodes)==1: continue	# node has no links - ignore

    allpoints.append([])
    points=allpoints[-1]
    lastnode=nodes[-1]
    for nodeno in range(len(nodes)):
        n=nodes[nodeno]
        # This is only the exterior of _this_ surface - there might
        # be other exterior links. Arrange in order.
        elinks=[]
        lastheading=radians(n.loc.headingto(nodes[(nodeno-1)%len(nodes)].loc))
        for link in n.links:
            # find links to the right
            for end in [0,1]:
                o=link.nodes[end]
                if o==n:
                    # We have a candidate
                    o=link.nodes[1-end]
                    h=radians(n.loc.headingto(o.loc))
                    if h>lastheading: h=h-twopi
                    elinks.append((o,h,link))
                    break
        if not ccw and nodeno==0:
            elinks.sort(lambda (o1,h1,l1),(o2,h2,l2): cmp(h1,h2))
        else:
            elinks.sort(lambda (o1,h1,l1),(o2,h2,l2): cmp(h2,h1)) # largest first
        if dump:
            print n.loc, "node, lastheading=", degrees(lastheading)
            for (n1,h1,link1) in elinks: print n1.loc, degrees(h1)
        if dump: dump.write("%.6f\t%.6f\n" % (n.loc.lon, n.loc.lat))

        # Accumulate points. Can't work out bezier points 'til have spacing.
        for i in range(len(elinks)):
            (n1,h1,link1)=elinks[i]
            if len(elinks)==1:
                (n2,h2,link2)=elinks[0]			# Stub
                link1.done+=1
            else:
                if n1==nodes[(nodeno+1)%len(nodes)]:
                    link1.done+=1
                if i and n1==nodes[(nodeno+1)%len(nodes)]:
                    break	# this is the next node
                else:	# link to same (i!=0) or different surface
                    (n2,h2,link2)=elinks[(i+1)%len(elinks)]
            if link1.nodes[0]==n1:
                end1=0
            else:
                end1=1
            if link2.nodes[0]==n2:
                end2=1
            else:
                end2=0
            code1=edgefeature(link1, end1, link2, end2)
            code2=edgefeature(link2, end2, link2, end2)

            straight=(h1-pi-h2)%twopi
            straight=straight<0.1 or straight>twopi-0.1	# arbitrary ~5degrees
            
            if n1==n2:
                # Stub
                w=link1.width/2
                loc=n.loc.biased((-cos(h2)-sin(h2))*w, (sin(h2)-cos(h2))*w)
                if dump: print loc, "stub", degrees(h1)
                points.append((loc, False, ""))	# no code
                loc=n.loc.biased((cos(h2)-sin(h2))*w, (-sin(h2)-cos(h2))*w)
                if dump: print loc, "stub", degrees(h1)
                points.append((loc, False, code2))
                break

            elif not i or n2==nodes[(nodeno+1)%len(nodes)]:
                # prev or next nodes
                
                if straight and link1 in subgraph and link2 in subgraph:	# arbitrary ~5degrees
                    w=(link1.width+link2.width)/4
                    # not quite average but close enough
                    intersect=n.loc.biased(-w*(cos(h1)+cos(h2-pi))/2,
                                            w*(sin(h1)+sin(h2-pi))/2)
                    if dump: print intersect, "straight", degrees(h1), degrees(h2), degrees((h1%twopi + (h2-pi)%twopi)/2)
                    points.append((intersect, False, code2))
                elif straight and link2.type=='RUNWAY':
                    # start of straight blank
                    intersect=n.loc.biased(-link2.width*cos(h2-pi)/2,
                                            link2.width*sin(h2-pi)/2)
                    if dump: print intersect, "straight startblank", degrees(h1), degrees(h2), degrees((h1%twopi + (h2-pi)%twopi)/2)
                    points.append((intersect, False, ''))
                elif straight and link1.type=='RUNWAY':
                    # end of straight blank
                    intersect=n.loc.biased(-link1.width*cos(h1)/2,
                                            link1.width*sin(h1)/2)
                    if dump: print intersect, "straight endblank", degrees(h1), degrees(h2), degrees((h1%twopi + (h2-pi)%twopi)/2)
                    points.append((intersect, False, code2))
                else:
                    ratio=0.5/sin((h1-pi)%twopi-h2)
                    intersect=n.loc.biased(-sin(h1)*link2.width*ratio - sin(h2)*link1.width*ratio,
                                           -cos(h1)*link2.width*ratio - cos(h2)*link1.width*ratio)
                    if dump: print intersect, "intersect", degrees(h1), degrees(h2), i,
                    if i and n2==nodes[(nodeno+1)%len(nodes)]:	# end of blank
                        if link1.type=='RUNWAY':
                            # special handling for runway ends
                            l1=max(0.0, min(link1.width, n.loc.distanceto(n1.loc)-link2.width/2))
                        elif not link1.draw:
                            # just draw straight line across exits to apron
                            l1=0.0
                            code1=''
                        else:
                            l1=link1.width
                        if l1:
                            l1=intersect.biased(sin(h1)*l1, cos(h1)*l1)
                            if dump: print "endblank",
                        #else:	# reduce to point
                        #    l1=0.0
                    else:
                        l1=link1.width
                        
                    if not i and n2!=nodes[(nodeno+1)%len(nodes)]:	# start of blank
                        if link2.type=='RUNWAY':
                            # special handling for runway ends
                            l2=max(0.0, min(link2.width, n.loc.distanceto(n2.loc)-link1.width/2))
                        elif not link2.draw:
                            # just draw straight line across exits to apron
                            l2=0.0
                            code1=''	# previous link
                        else:
                            l2=link2.width
                        if l2:
                            l2=intersect.biased(sin(h2)*l2, cos(h2)*l2)
                            if dump: print "startblank",
                        else:	# reduce to point
                            #l2=0.0
                            code2=''
                    else:
                        l2=link2.width

                    if dump: print
                    points.append((intersect, (l1, l2), (code1,code2)))

# --------------------------------------------------------------------------

def tessbegin(datatype, data):
    if datatype!=GL_LINE_LOOP: raise GLUerror	# can't happen
    (out, dump)=data
    if dump: print "Begin"
    
def tessvertex(vertex, data):
    (out, dump)=data
    (pt, bez, blank, code)=vertex
    if dump: print "Vertex", pt, bez, blank, code
    if not pt: return	# dummy bezier vertex for outscribing obtuse curves
    if blank==True:	# end of blank
        out.append(AptNav(111, "%10.6f %11.6f" % (pt.lat, pt.lon)))
    if bez:
        out.append(AptNav(112, "%10.6f %11.6f %10.6f %11.6f %s" % (
            pt.lat, pt.lon, bez.lat, bez.lon, code)))
    else:
        out.append(AptNav(111, "%10.6f %11.6f %s" % (pt.lat, pt.lon, code)))
    if blank==False:	# start of blank
        out.append(AptNav(111, "%10.6f %11.6f" % (pt.lat, pt.lon)))

def tesscombine(coords, vertex, weight, data):
    (out, dump)=data
    if dump:
        print "Combine", Point(coords[2], coords[0])
        for i in range(len(weight)):
            if not weight[i]: break
            (pt, bez, blank, code)=vertex[i]
            print pt, bez, blank, code, weight[i]
        #if blank!=None:
        #    # hack. Collapse blank sections to a point
        #    vertex[i]=(pt, None, None, code)
    (pt, bez, blank, code)=vertex[0]	# arbitrary - use first code
    return (Point(coords[2], coords[0]), None, None, code)

def tessend(data):
    (out, dump)=data
    if dump: print "End"
    out[-1].code+=2		# Terminate last


# --------------------------------------------------------------------------

def taxilayout(allnodes, alllinks, surfaceheading, output, aptdat=None, ident="unknown"):

    # Edges ----------------------------------------------------------------

    dump=(output.debug and ident=="HECA" and open(join(output.xppath, ident+"_nodes.txt"), "at"))
    if dump:
        print ident
        interfile=open(join(output.xppath, ident+"_inter.txt"), "at")

    # Output points and bezier control points
    tessObj = gluNewTess()
    gluTessNormal(tessObj, 0, -1, 0)
    gluTessProperty(tessObj,GLU_TESS_WINDING_RULE,GLU_TESS_WINDING_NONZERO)
    gluTessProperty(tessObj,GLU_TESS_BOUNDARY_ONLY,GL_TRUE)
    gluTessCallback(tessObj,GLU_TESS_BEGIN_DATA,   tessbegin)
    gluTessCallback(tessObj,GLU_TESS_VERTEX_DATA,  tessvertex)
    gluTessCallback(tessObj,GLU_TESS_END_DATA,     tessend)
    gluTessCallback(tessObj,GLU_TESS_COMBINE_DATA, tesscombine)

    # Candidates
    links=[l for l in alllinks if l.width>1 and (l.draw or l.lights[0] or l.lights[1] or l.lines[0]!='NONE' or l.lines[1]!='NONE') and (not aptdat or (not output.excluded(l.nodes[0].loc) and not output.excluded(l.nodes[1].loc)))]

    while links:
        basepoints=[]

        # Find an independent subgraph by looking for connected links
        subgraph=[links[0]]	# start with random node
        surface=links[0].surface
        links.pop(0)
        subgraph[0].findlinked(links, subgraph)
        #if len(subgraph)<=1 and len(subgraph[0].links==0):
        #    continue	# orphan node - don't generate apt.dat entry

        # Exterior
        follow(subgraph, True, basepoints, dump)

        # Interior(s)
        lastlen=maxint
        while True:
            interior=[link for link in subgraph if link.done<2]
            if not interior: break
            if len(interior)==lastlen: break	# prevent infloop on error
            follow(interior, False, basepoints, dump)
            lastlen=len(interior)

        out=[AptNav(110, "%02d %4.2f %6.2f Taxiways" % (
            surface, 0.25, surfaceheading))]
        if dump: print "BeginPolygon"
        gluTessBeginPolygon(tessObj, (out, dump))
        for points in basepoints:
            gluTessBeginContour(tessObj)
            for i in range(len(points)):
                (loc, bez, code)=points[i]
                loc.round()
                if dump: interfile.write("%.6f\t%.6f\n" % (loc.lon,loc.lat))
                if not bez:
                    gluTessVertex(tessObj, [loc.lon, 0, loc.lat], (loc, None, None, code))
                    
                else:	# pair of beziers. loc is intersection point
                    (l1,l2)=bez		# desired distances to control points
                    h1=None
                    (code1,code2)=code
                    if type(l1)==float:
                        (oloc, obez, ocode)=points[(i-1)%len(points)]
                        if not l1:	# reduces to a point
                            gluTessVertex(tessObj, [loc.lon, 0, loc.lat], (loc, None, None, code1))
                        elif l1<loc.distanceto(oloc)/2 or not obez:
                            # Skip duplicate truncated section
                            l1=min(l1,loc.distanceto(oloc)/2)
                            h1=radians(loc.headingto(oloc))
                            p1=loc.biased(sin(h1)*l1, cos(h1)*l1).round()
                            gluTessVertex(tessObj, [p1.lon, 0, p1.lat], (p1, p1+(loc-p1)*(2.0/3), None, code1))
                    else:		# absolute location of control point
                        p1=l1.round()	# end of blank section
                        if not p1.equals(loc) and type(l2)==float and l2:
                            h1e=radians(loc.headingto(p1))
                            (oloc, obez, ocode)=points[(i+1)%len(points)]
                            h2=radians(loc.headingto(oloc))
                            if dump: print "endblank", degrees((h1e-h2)%twopi)
                            if (h1e-h2)%twopi<=pi/2:
                                # fill fillet
                                if dump: print loc, "filler", degrees((h1e-h2)%twopi)
                                gluTessVertex(tessObj, [loc.lon, 0, loc.lat], (loc, None, None, ''))                                
                        gluTessVertex(tessObj, [p1.lon, 0, p1.lat], (p1, p1+(loc-p1)*(2.0/3), True, code1))

                    if type(l2)==float:
                        if not l2:	# reduces to a point
                            gluTessVertex(tessObj, [loc.lon, 0, loc.lat], (loc, None, None, code2))
                        else:
                            (oloc, obez, ocode)=points[(i+1)%len(points)]
                            l2=min(l2,loc.distanceto(oloc)/2)
                            h2=radians(loc.headingto(oloc))
                            p2=loc.biased(sin(h2)*l2, cos(h2)*l2).round()
                            if h1!=None and (h1-h2)%twopi>pi:
                                # generate dummy vertices to outscribe curve
                                b1=(p1+(loc-p1)*(2.0/3)).round()
                                b2=(p2+(loc-p2)*(2.0/3)).round()
                                if dump: print loc, "obtuse", b1, b2
                                gluTessVertex(tessObj, [b1.lon, 0, b1.lat], (None, None, None, code1))
                                gluTessVertex(tessObj, [b2.lon, 0, b2.lat], (None, None, None, code2))
                            gluTessVertex(tessObj, [p2.lon, 0, p2.lat], (p2, p2-(loc-p2)*(2.0/3), None, code2))
                    else:		# absolute location of control point
                        p2=l2.round()	# start of blank section
                        gluTessVertex(tessObj, [p2.lon, 0, p2.lat], (p2, p2-(loc-p2)*(2.0/3), False, ''))
                        if h1!=None and not p2.equals(loc):
                            h2=radians(loc.headingto(p2))
                            if dump: print "startblank", degrees((h1-h2)%twopi)
                            if (h1-h2)%twopi<=pi/2:
                                # fill fillet
                                if dump: print loc, "filler", degrees((h1-h2)%twopi)
                                gluTessVertex(tessObj, [loc.lon, 0, loc.lat], (loc, None, None, ''))
            gluTessEndContour(tessObj)

        gluTessEndPolygon(tessObj)
        if dump: print "EndPolygon\n"
        if aptdat:
            aptdat.extend(out)
        else:
            output.misc.append((110, subgraph[0].nodes[0].loc, out))

    gluDeleteTess(tessObj)


    # Centre lines ---------------------------------------------------------

    # Candidates - have at least one link with a centre line or lights
    links=[l for l in alllinks if (l.centreline or l.centrelights) and (not aptdat or (not output.excluded(l.nodes[0].loc) and not output.excluded(l.nodes[1].loc)))]
    for n in allnodes:
        n.donecross=[[True for i in n.links] for i in n.links]
        if aptdat and output.excluded(n.loc): continue
        for i in range(len(n.links)):
            for j in range(len(n.links)):
                if i!=j and (n.links[i].centreline or n.links[i].centrelights):
                    if n.links[j].type=='RUNWAY':
                        for end in [0,1]:
                            if n!=n.links[j].nodes[end] and len(n.links[j].nodes[end].links)>1: break	# no cross for runway end
                        else:
                            continue
                    n.donecross[i][j]=n.donecross[j][i]=False

    # First do proper links, opportunistically adding crosses
    while links:
        stuff=[]

        # Look for a real end link - no other links at all from end node
        for link in links:
            for startend in [0,1]:
                if len(link.nodes[startend].links)==1:
                    break	# found one
            else:
                continue
            break
        else:
            # Look for an end link - no other valid links from end node
            for link in links:
                for startend in [0,1]:
                    for l in link.nodes[startend].links:
                        if link!=l and l in links and link.name==l.name and link.centreline==l.centreline and link.centrelights==l.centrelights:
                            break	# valid continuation - no good - goto A
                    else:
                        break	# found one - goto B
                else:
                    continue	# A
                break		# B
            else:
                # Only loops left - just pick first link
                link=links[0]
                startend=0

        if link.centreline:
            out=[AptNav(120,"Centreline for %s"  %link.name)]
            if link.type=='VEHICLE':
                code="22"
            else:
                code="51"
            if link.centrelights:
                code=code+" 101"
        else:
            out=[AptNav(120,"Centrelights for %s"%link.name)]
            code="101"

        # Control points are min(width, length/2)   along
        # Bezier  points are min(width, length/2)/3 along

        # Look for a cross before first node
        n=link.nodes[startend]	# start node
        i=n.links.index(link)
        for j in range(len(n.links)):
            if not n.donecross[i][j] and (link.centreline or not n.links[j].centreline) and (link.centrelights or not n.links[j].centrelights):
                n.donecross[i][j]=n.donecross[j][i]=True
                for end in [0,1]:
                    o=n.links[j].nodes[end]	# end node
                    if o!=n: break
                length=n.loc.distanceto(o.loc)
                if len(o.links)==1:
                    if length<link.width:
                        ctrl=1
                    else:
                        ctrl=link.width/length
                elif length>2*n.links[j].width:
                    ctrl=n.links[j].width/length
                else:
                    ctrl=0.5
                stuff.extend(bezpt(out, n.loc, o.loc, ctrl, 1,code,"0"))
                break

        # Follow path
        while True:
            n=link.nodes[startend]	# start node
            o=link.nodes[1-startend]	# next node
            length=n.loc.distanceto(o.loc)
            if len(n.links)==len(o.links)==1:
                out.append(AptNav(111, "%10.6f %11.6f %s" % (
                    n.loc.lat, n.loc.lon, code)))
                stuff.append(AptNav(20, "%10.6f %11.6f 0 0 5 %s" % (
                    n.loc.lat, n.loc.lon, "{@R}1")))
                out.append(AptNav(111, "%10.6f %11.6f %s" % (
                    o.loc.lat, o.loc.lon, code)))
                stuff.append(AptNav(20, "%10.6f %11.6f 0 0 5 %s" % (
                    o.loc.lat, o.loc.lon, "{@R}2")))
            elif len(n.links)==1:
                if length>link.width:
                    out.append(AptNav(111, "%10.6f %11.6f %s" % (
                        n.loc.lat, n.loc.lon, code)))
                    stuff.append(AptNav(20, "%10.6f %11.6f 0 0 5 %s" %(
                        n.loc.lat, n.loc.lon, "{@R}3")))
                stuff.extend(bezpt(out, o.loc, n.loc, min(1,link.width/length), 1, code, "4"))
            elif len(o.links)==1:
                stuff.extend(bezpt(out, n.loc, o.loc, min(1,link.width/length), 5, code, "5"))
                if length>link.width:
                    out.append(AptNav(111, "%10.6f %11.6f %s" % (
                        o.loc.lat, o.loc.lon, code)))
                    stuff.append(AptNav(20, "%10.6f %11.6f 0 0 5 %s" %(
                        o.loc.lat, o.loc.lon, "{@R}6")))
            elif length>2*link.width:
                stuff.extend(bezpt(out, n.loc, o.loc, link.width/length, 5, code, "7"))
                stuff.extend(bezpt(out, o.loc, n.loc, link.width/length, 1, code, "8"))
            else:
                stuff.extend(bezpt(out, n.loc, o.loc, 0.5, 5, code,"9"))
            links.remove(link)

            # Look for next link - greedy
            for l in o.links:
                if l in links and link.name==l.name and link.type==l.type and link.centreline==l.centreline and link.centrelights==l.centrelights:
                    i=o.links.index(link)
                    j=o.links.index(l)
                    o.donecross[i][j]=o.donecross[j][i]=True
                    link=l
                    for startend in [0,1]:
                        if link.nodes[startend]==o: break
                    break	# found one
            else:
                break	# didn't find one

        # Look for a cross at end node
        n=o		# start node
        i=n.links.index(link)
        for j in range(len(n.links)):
            if not n.donecross[i][j] and (link.centreline or not n.links[j].centreline) and (link.centrelights or not n.links[j].centrelights):
                n.donecross[i][j]=n.donecross[j][i]=True
                for end in [0,1]:
                    o=n.links[j].nodes[end]	# end node
                    if o!=n: break
                length=n.loc.distanceto(o.loc)
                if len(o.links)==1:
                    if length<link.width:
                        ctrl=1
                    else:
                        ctrl=link.width/length
                elif length>2*n.links[j].width:
                    ctrl=n.links[j].width/length
                else:
                    ctrl=0.5
                stuff.extend(bezpt(out, n.loc, o.loc, ctrl, 5,code,"-"))
                break

        # Terminate last
        if out[-1].code==111:
            out[-1].code=115
            out[-1].text=out[-1].text[:22]
        else:
            out[-1].code=116
            out[-1].text=out[-1].text[:45]
        if aptdat:
            aptdat.extend(out)
        else:
            output.misc.append((120, n.loc, out))

        if False:	# XXX debug
            stuff[0].text=stuff[0].text[:31]+'B'+stuff[0].text[32:]
            stuff[-1].text=stuff[-1].text[:31]+'L'+stuff[-1].text[32:]
            if aptdat:
                aptdat.extend(stuff)
            else:
                output.misc.append((120, n.loc, stuff))

    # Fill in rest of the crosses
    for n in allnodes:
        for i in range(len(n.links)):
            for j in range(len(n.links)):
                if n.donecross[i][j]:
                    continue
                stuff=[]
                n.donecross[i][j]=n.donecross[j][i]=True
                if n.links[i].centreline or n.links[j].centreline:
                    name="Centreline"
                    if n.links[i].type!='VEHICLE' and n.links[j].type!='VEHICLE':
                        code="51"
                    else:
                        code="22"
                    if n.links[i].centrelights or n.links[j].centrelights:
                        code=code+" 101"
                else:
                    name="Centrelights"
                    code="101"
                if n.links[i].name==n.links[j].name or n.links[j].name.startswith("Runway"):
                    out=[AptNav(120,"%s for %s"  % (name, n.links[i].name))]
                elif n.links[i].name.startswith("Runway"):
                    out=[AptNav(120,"%s for %s"  % (name, n.links[j].name))]
                else:
                    out=[AptNav(120,"%s for Taxi join" % name)]

                a=b=n
                for end in [0,1]:
                    if a==n: a=n.links[i].nodes[end]
                    if b==n: b=n.links[j].nodes[end]

                for (link,o,z) in [(n.links[i],a,1),(n.links[j],b,5)]:
                    length=n.loc.distanceto(o.loc)
                    if len(o.links)==1:
                        if length<link.width:
                            ctrl=1
                        else:
                            ctrl=link.width/length
                    elif length>2*link.width:
                        ctrl=link.width/length
                    else:
                        ctrl=0.5
                    stuff.extend(bezpt(out, n.loc, o.loc, ctrl, z, code, "X"))
                # Terminate last
                out[-1].code=116
                out[-1].text=out[-1].text[:45]
                if aptdat:
                    aptdat.extend(out)
                else:
                    output.misc.append((120, n.loc, out))

                if False:	# XXX debug
                    if aptdat:
                        aptdat.extend(stuff)
                    else:
                        output.misc.append((20, n.loc, stuff))


    # Startup and hold marks -----------------------------------------------
    for n in allnodes:
        if aptdat and output.excluded(n.loc): continue
        if n.type in ['HOLD_SHORT','ILS_HOLD_SHORT']:
            if not n.links: continue
            # Find a link that starts at this node
            for link in n.links:
                if link.nodes[0]==n:
                    h=n.loc.headingto(link.nodes[1].loc)
                    #if dump: print n.loc, n.type, "forward", h,
                    break
            else:	# No link starts at this node - reverse
                link=n.links[0]
                h=link.nodes[0].loc.headingto(n.loc)
                #if dump: print n.loc, n.type, "backward", h,
            out=[AptNav(120, "%s hold short" % link.name)]
            #if dump: print "reverse=", n.reverse
            if n.reverse: h=h+180
            h=radians(h%360)
            w=max(1, link.width/2-0.5)
            if n.type=='HOLD_SHORT':
                code="54"
            else:
                code="56 103"
            loc=n.loc.biased(-cos(h)*w, sin(h)*w)
            out.append(AptNav(111, "%10.6f %11.6f %s" % (
                loc.lat, loc.lon, code)))
            loc=n.loc.biased(cos(h)*w, -sin(h)*w)
            out.append(AptNav(115, "%10.6f %11.6f" % (
                loc.lat, loc.lon)))
            if aptdat:
                aptdat.extend(out)
            else:
                output.misc.append((120, n.loc, out))            
            
        elif n.parking:	# TaxiwayParking
            for link in n.links:
                if not link.centreline: continue
                if n.startup:
                    out=[AptNav(120, n.startup)]
                else:
                    out=[AptNav(120, link.name)]
                for end in [0,1]:
                    o=link.nodes[end]
                    if o!=n: break
                h=radians(n.loc.headingto(o.loc))
                w=link.width/4
                if n.type=='VEHICLE':
                    code="22"	# not sure what to do
                else:
                    code="51"
                loc=n.loc.biased(-cos(h)*w, sin(h)*w)
                out.append(AptNav(111, "%10.6f %11.6f %s" % (
                    loc.lat, loc.lon, code)))
                loc=n.loc.biased(cos(h)*w, -sin(h)*w)
                out.append(AptNav(115, "%10.6f %11.6f" % (
                    loc.lat, loc.lon)))
                if aptdat:
                    aptdat.extend(out)
                else:
                    output.misc.append((120, n.loc, out))            
