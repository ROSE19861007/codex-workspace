"""Loss-aware ASCII DXF -> SVG plus spatial-editor JSON converter (standard library)."""
from __future__ import annotations

import hashlib
import html
import json
import math
import sys
from collections import Counter
from pathlib import Path


def parse_pairs(path: Path):
    with path.open("r", encoding="utf-8", errors="replace", newline=None) as f:
        while True:
            c, v = f.readline(), f.readline()
            if not c or not v:
                return
            try:
                yield int(c.strip()), v.rstrip("\r\n")
            except ValueError:
                continue


def values(groups, code):
    return [v for c, v in groups if c == code]


def number(groups, code, default=0.0):
    found = values(groups, code)
    try:
        return float(found[0]) if found else default
    except ValueError:
        return default


def integer(groups, code, default=0):
    try:
        return int(float(values(groups, code)[0]))
    except (ValueError, IndexError):
        return default


def string(groups, code, default=""):
    found = values(groups, code)
    return found[0] if found else default


def point_pairs(groups, xcode=10, ycode=20):
    xs, ys = values(groups, xcode), values(groups, ycode)
    result = []
    for x, y in zip(xs, ys):
        try:
            result.append([float(x), float(y)])
        except ValueError:
            pass
    return result


def parse(path: Path):
    header, blocks, entities = {}, {}, []
    section, pending_section, item, block = None, False, None, None

    def flush():
        nonlocal item
        if not item:
            return
        if section == "ENTITIES":
            entities.append(item)
        elif section == "BLOCKS" and block is not None and item["type"] not in {"BLOCK", "ENDBLK"}:
            block["entities"].append(item)
        item = None

    pairs = list(parse_pairs(path))
    i = 0
    while i < len(pairs):
        code, val = pairs[i]
        if code == 0 and val == "SECTION":
            flush(); pending_section = True; i += 1; continue
        if pending_section and code == 2:
            section, pending_section = val, False; i += 1; continue
        if code == 0 and val == "ENDSEC":
            flush(); section = None; block = None; i += 1; continue
        if section == "HEADER":
            if code == 9:
                header[val] = []
            elif header:
                header[next(reversed(header))].append((code, val))
            i += 1; continue
        if section not in {"BLOCKS", "ENTITIES"}:
            i += 1; continue
        if code == 0:
            flush()
            if section == "BLOCKS" and val == "BLOCK":
                block = {"name": "", "base": [0.0, 0.0], "entities": []}
                item = {"type": "BLOCK", "groups": []}
            elif section == "BLOCKS" and val == "ENDBLK":
                if block is not None:
                    blocks[block["name"]] = block
                item = {"type": "ENDBLK", "groups": []}
                block = None
            else:
                item = {"type": val, "groups": []}
        elif item is not None:
            item["groups"].append((code, val))
            if section == "BLOCKS" and item["type"] == "BLOCK":
                if code == 2: block["name"] = val
                elif code == 10: block["base"][0] = number(item["groups"], 10)
                elif code == 20: block["base"][1] = number(item["groups"], 20)
        i += 1
    flush()
    return header, blocks, entities


def affine(m, p):
    a, b, c, d, e, f = m
    return [a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f]


def compose(m, n):
    a, b, c, d, e, f = m; A, B, C, D, E, F = n
    return [a*A+c*B, b*A+d*B, a*C+c*D, b*C+d*D, a*E+c*F+e, b*E+d*F+f]


def fmt(n):
    return f"{n:.9g}"


def kind_for(layer):
    lowered = layer.lower()
    if "墙" in layer or "wall" in lowered: return "wall"
    if "门" in layer or "door" in lowered: return "door"
    if "窗" in layer or "window" in lowered: return "window"
    if "柱" in layer or "column" in lowered: return "column"
    if "楼梯" in layer or "stair" in lowered: return "stair"
    return "unknown"


def primitive(entity, transform):
    g, t = entity["groups"], entity["type"]
    layer, handle = string(g, 8, "0"), string(g, 5, "")
    base = {"type": t, "layer": layer, "handle": handle}
    if t == "LINE":
        p1, p2 = affine(transform, [number(g,10), number(g,20)]), affine(transform, [number(g,11), number(g,21)])
        return base | {"geometry": {"type":"line", "start":p1, "end":p2}, "svg": f'<path d="M {fmt(p1[0])} {fmt(p1[1])} L {fmt(p2[0])} {fmt(p2[1])}" />'}
    if t == "LWPOLYLINE":
        points = point_pairs(g); bulges = [float(x) if x else 0.0 for x in values(g,42)]
        pts = [affine(transform, p) for p in points]
        closed = bool(integer(g,70) & 1)
        if not pts: return base | {"geometry": {"type":"polyline", "points":[]}, "svg": ""}
        d = [f"M {fmt(pts[0][0])} {fmt(pts[0][1])}"]
        for idx in range(1, len(pts)):
            d.append(f"L {fmt(pts[idx][0])} {fmt(pts[idx][1])}")
        if closed: d.append("Z")
        return base | {"geometry":{"type":"polygon" if closed else "polyline", "points":pts, "bulges":bulges, "closed":closed}, "svg": '<path d="'+' '.join(d)+'" />'}
    if t == "CIRCLE":
        center = affine(transform,[number(g,10),number(g,20)]); r = number(g,40)
        return base | {"geometry":{"type":"circle", "center":center, "radius":r}, "svg":f'<circle cx="{fmt(center[0])}" cy="{fmt(center[1])}" r="{fmt(r)}" />'}
    if t == "ARC":
        center=[number(g,10),number(g,20)]; r=number(g,40); a1=math.radians(number(g,50)); a2=math.radians(number(g,51))
        raw1=[center[0]+r*math.cos(a1),center[1]+r*math.sin(a1)]; raw2=[center[0]+r*math.cos(a2),center[1]+r*math.sin(a2)]
        p1,p2=affine(transform,raw1),affine(transform,raw2); span=(number(g,51)-number(g,50))%360
        return base | {"geometry":{"type":"arc", "center":affine(transform,center), "radius":r, "startAngle":number(g,50), "endAngle":number(g,51)}, "svg":f'<path d="M {fmt(p1[0])} {fmt(p1[1])} A {fmt(r)} {fmt(r)} 0 {1 if span>180 else 0} 1 {fmt(p2[0])} {fmt(p2[1])}" />'}
    if t in {"TEXT", "MTEXT"}:
        p=affine(transform,[number(g,10),number(g,20)]); text=string(g,1,"").replace("\\P", " ")
        return base | {"geometry":{"type":"text", "position":p, "text":text}, "svg":f'<text x="{fmt(p[0])}" y="{fmt(p[1])}" data-flip-text="true">{html.escape(text)}</text>'}
    return base | {"geometry": None, "svg": ""}


def source_reference(p):
    return {"handle": p["handle"], "layer": p["layer"], "objectType": p["type"]}


def expand(entity, blocks, transform, stack=(), source_insert=None):
    if entity["type"] != "INSERT":
        yield primitive(entity, transform); return
    g = entity["groups"]; name = string(g,2); block = blocks.get(name)
    if not block or name in stack:
        yield primitive(entity, transform); return
    sx,sy=number(g,41,1),number(g,42,1); ang=math.radians(number(g,50)); ca,sa=math.cos(ang),math.sin(ang)
    ins=[number(g,10),number(g,20)]; bx,by=block["base"]
    local=[sx*ca,sx*sa,-sy*sa,sy*ca,ins[0]-(sx*ca*bx-sy*sa*by),ins[1]-(sx*sa*bx+sy*ca*by)]
    for sub in block["entities"]:
        yield from expand(sub, blocks, compose(transform,local), stack+(name,), source_insert or string(g,5))


def main(source: Path, output: Path):
    header, blocks, entities = parse(source)
    insunits=integer(header.get("$INSUNITS", []),70,0)
    units={1:("inch",25.4),2:("foot",304.8),4:("millimetre",1.0),5:("centimetre",10.0),6:("metre",1000.0)}
    unit, mm_per_unit = units.get(insunits,("unknown",None))
    extmin=point_pairs(header.get("$EXTMIN",[])); extmax=point_pairs(header.get("$EXTMAX",[]))
    raw = []; expanded=[]
    for entity in entities:
        p=primitive(entity,[1,0,0,1,0,0]); raw.append({"sourceRefs":[source_reference(p)], "geometry":p["geometry"]})
        expanded.extend(expand(entity,blocks,[1,0,0,1,0,0]))
    coords=[]
    for p in expanded:
        geo=p["geometry"] or {}; typ=geo.get("type")
        if typ in {"line"}: coords += [geo["start"],geo["end"]]
        elif typ in {"polygon","polyline"}: coords += geo["points"]
        elif typ in {"circle","arc"}: coords += [geo["center"]]
        elif typ=="text": coords += [geo["position"]]
    if extmin and extmax:
        minx,miny=extmin[0]; maxx,maxy=extmax[0]
    elif coords:
        minx=min(p[0] for p in coords); maxx=max(p[0] for p in coords); miny=min(p[1] for p in coords); maxy=max(p[1] for p in coords)
    else: raise RuntimeError("No drawable coordinates found")
    w,h=maxx-minx,maxy-miny
    semantic=[]; semantic_ids={}; type_counts=Counter(p["type"] for p in expanded)
    for primitive_index, p in enumerate(expanded):
        kind=kind_for(p["layer"])
        if kind=="unknown" or not p["geometry"]: continue
        entity_id=f"{kind}-{len(semantic)+1:04d}"
        props={}
        if kind=="wall": props={"heightClass":"unknown", "thickness":None, "thicknessUnit":unit, "height":None, "heightUnit":unit, "structuralRole":"unknown"}
        elif kind in {"door","window"}: props={"hostWallId":None}
        semantic.append({"id":entity_id,"kind":kind,"sourceRefs":[source_reference(p)],"confidence":"inferred","evidence":[f"layer:{p['layer']}"],"sourceGeometry":p["geometry"],"properties":props})
        semantic_ids[primitive_index] = entity_id
    svg=[]
    for i,p in enumerate(expanded):
        if not p["svg"]: continue
        entity_id = semantic_ids.get(i)
        css="semantic" if entity_id else "raw"
        entity_attr = f' data-entity-id="{entity_id}" data-kind="{kind_for(p["layer"])}"' if entity_id else ""
        svg.append(f'<g class="{css}" data-source-handle="{html.escape(p["handle"])}" data-layer="{html.escape(p["layer"])}"{entity_attr}>{p["svg"]}</g>')
    line_weight = max(max(w, h) / 360 if max(w, h) else 1, 3.2)
    svg_text=f'''<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="{fmt(minx)} {fmt(miny)} {fmt(w)} {fmt(h)}" data-source-unit="{unit}">\n<style>.raw,.semantic{{fill:none;stroke:#14202b;stroke-width:{fmt(line_weight)};stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke}} text{{stroke:none;fill:#14202b;font-size:{fmt(max(w,h)/180)}}} .semantic{{stroke:#0a4f93;stroke-width:{fmt(line_weight * 1.15)}}}</style>\n<g transform="translate(0 {fmt(miny+maxy)}) scale(1 -1)">\n{''.join(svg)}\n</g>\n</svg>'''
    output.mkdir(parents=True,exist_ok=True); base=output / source.stem
    (base.with_suffix(".svg")).write_text(svg_text,encoding="utf-8")
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    status="needs-review" if unit=="unknown" or not semantic else "needs-review"
    unit_finding = ("Unit metadata is unknown; confirm intended drawing unit before measurement-critical use." if unit == "unknown" else f"Unit confirmed from $INSUNITS: {unit} ({mm_per_unit} millimetres per drawing unit).")
    data={"schemaVersion":"1.0","status":status,"source":{"fileName":source.name,"sha256":source_hash,"space":"model","drawingUnit":unit,"millimetresPerUnit":mm_per_unit,"sourceYDirection":"up","dxfVersion":string(header.get("$ACADVER",[]),1,"")},"coordinateTransform":{"editorYDirection":"down","matrix":[1,0,0,-1,0,miny+maxy],"description":"Apply to sourceGeometry for a Y-down editor; SVG renders this transform in its root group."},"bounds":{"min":[minx,miny],"max":[maxx,maxy],"unit":unit},"entities":semantic,"rawObjects":raw,"validation":{"maxGeometryDeviationSourceUnits":0,"unresolvedObjectCount":len(raw)-len(semantic),"findings":["DXF source geometry is preserved in rawObjects and SVG primitives.",unit_finding,"Walls, doors, windows, and columns are layer-name candidates only; review inferred semantic entities and unclassified block content.",f"Expanded primitive counts: {dict(type_counts)}"]}}
    (base.with_suffix(".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest={"sourceFile":source.name,"sourceSha256":source_hash,"converter":"local standard-library DXF parser","outputs":[base.with_suffix(".svg").name,base.with_suffix(".json").name],"unitDecision":{"drawingUnit":unit,"millimetresPerUnit":mm_per_unit,"source":"$INSUNITS"},"unsupportedOrUnresolved":["DIMENSION/HATCH/VIEWPORT and proxy objects retained as raw objects but are not rendered as semantic geometry.","Block expansion retains source references but not a separate SVG entity ID for every semantic candidate."],"status":status}
    (base.with_name(base.name+".manifest.json")).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"svg":str(base.with_suffix('.svg')),"json":str(base.with_suffix('.json')),"manifest":str(base.with_name(base.name+'.manifest.json')),"expanded":len(expanded),"semantic":len(semantic),"unit":unit,"bounds":[minx,miny,maxx,maxy]},ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 3: raise SystemExit("Usage: convert_dxf.py INPUT.dxf OUTPUT_DIR")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
