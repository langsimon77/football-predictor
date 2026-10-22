import re, json, glob, os, unicodedata, datetime as dt
import pandas as pd
import paths
FD=str(paths.SOURCES)
MON={m:i+1 for i,m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
DATE_RE=re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
SCORE_RE=re.compile(r"\s(\d+)-(\d+)\s*(?:pen\.\s*(\d+)-(\d+)\s*)?(a\.e\.t\.)?\s*(?:\(([^)]*)\))?\s*$")
def season_years(fname):
    m=re.search(r"(\d{4})-(\d{2})",fname)
    if m: return int(m.group(1)), int(m.group(1))+1
    m=re.search(r"(\d{4})",fname); return int(m.group(1)), int(m.group(1))
def parse_txt(path, comp, default_cc=None):
    y1,y2=season_years(path)
    out=[]; cur=None; year=None
    for line in open(path,encoding="utf-8"):
        line=line.rstrip("\n")
        m=DATE_RE.match(line)
        if m:
            mon=MON[m.group(1)]; d=int(m.group(2))
            if m.group(3): year=int(m.group(3))
            elif year is None: year=y1 if mon>=7 else y2
            else:
                # infer year rollover
                cand=year
                if cur and mon<cur.month-3: cand=year+1
                year=cand
            cur=dt.date(year,mon,d); continue
        if " v " not in line or cur is None: continue
        body=re.sub(r"^\s*(\d{1,2}[:.]\d{2})?\s*","",line)
        # split score
        if "-" not in body: continue
        # extract trailing score segment
        mm=re.search(r"\s(\d+-\d+.*)$", body.split(" v ",1)[1])
        if not mm: continue
        right=body.split(" v ",1)[1]; seg=mm.group(1); away=right[:mm.start()].strip()
        home=body.split(" v ",1)[0].strip()
        nums=re.findall(r"(\d+)-(\d+)",seg)
        if not nums: continue
        if "a.e.t" in seg:
            par=re.search(r"\(([^)]*)\)",seg)
            if par:
                ps=re.findall(r"(\d+)-(\d+)",par.group(1)); hg,ag=map(int,ps[0])
            else: continue
        else:
            # "pen." without a.e.t. unlikely; first score is ft
            if "pen" in seg:
                # format "x-y pen. a-b" -> second is ft
                hg,ag=map(int,nums[1])
            else: hg,ag=map(int,nums[0])
        def cc(t):
            m=re.search(r"\(([A-Z]{3})\)\s*$",t)
            return (re.sub(r"\s*\([A-Z]{3}\)\s*$","",t).strip(), m.group(1) if m else default_cc)
        h,hc=cc(home); a,ac=cc(away)
        if not hc or not ac: continue
        if cur.year>y2 or (cur.year==y2 and cur.month>8 and y1!=y2): continue
        out.append(dict(date=cur.isoformat(),home=h,away=a,hcc=hc,acc=ac,hg=hg,ag=ag,comp=comp,src=os.path.basename(path)))
    return out
if __name__=="__main__":
    r=parse_txt(FD+"/champions-league/2024-25/el.txt","UEL")
    print(len(r), r[:2], r[-1])
    r=parse_txt(FD+"/europe/croatia/2024-25_hr1.txt","DOM","CRO"); print(len(r), r[:2], r[-1])
