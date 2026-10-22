import re, json, glob, os, unicodedata, difflib, collections
import pandas as pd
from parse import parse_txt
import euro2627
import paths
FD=str(paths.SOURCES); START="2021-07-01"
DIV={"E0":"ENG","SP1":"ESP","I1":"ITA","F1":"FRA","D1":"GER","T1":"TUR","N1":"NED","P1":"POR","B1":"BEL","SC0":"SCO","G1":"GRE","ROM":"ROU","POL":"POL","SWE":"SWE","NOR":"NOR","DEN":"DEN","IRL":"IRL","FIN":"FIN","AUT":"AUT","SUI":"SUI",
     "E1":"ENG","SP2":"ESP","I2":"ITA","F2":"FRA","D2":"GER"}
FOLDER={"albania":"ALB","andorra":"AND","armenia":"ARM","azerbaijan":"AZE","belarus":"BLR","bosnia-herzegovina":"BIH","bulgaria":"BUL","croatia":"CRO","cyprus":"CYP","czech-republic":"CZE","denmark":"DEN","estonia":"EST","faroe-islands":"FRO","finland":"FIN","france":"FRA","georgia":"GEO","gibraltar":"GIB","greece":"GRE","hungary":"HUN","iceland":"ISL","ireland":"IRL","kosovo":"KOS","latvia":"LVA","liechtenstein":"LIE","lithuania":"LTU","luxembourg":"LUX","malta":"MLT","moldova":"MDA","montenegro":"MNE","netherlands":"NED","north-macedonia":"MKD","northern-ireland":"NIR","norway":"NOR","poland":"POL","portugal":"POR","romania":"ROU","russia":"RUS","san-marino":"SMR","scotland":"SCO","serbia":"SRB","slovakia":"SVK","slovenia":"SVN","sweden":"SWE","switzerland":"SUI","turkey":"TUR","ukraine":"UKR","wales":"WAL"}
FJ={"at":"AUT","be":"BEL","de":"GER","en":"ENG","es":"ESP","fr":"FRA","gr":"GRE","it":"ITA","nl":"NED","pt":"POR","sco":"SCO","tr":"TUR"}
rows=[]
m=pd.read_csv(FD+"/Club-Football-Match-Data/data/Matches.csv",low_memory=False)
m=m[(m.MatchDate>=START)&m.Division.isin(DIV.keys())&m.FTHome.notna()]
END={}
for dv,mx in m.groupby("Division").MatchDate.max().items():
    if dv in ("E1","SP2","I2","F2","D2"): continue
    END[DIV[dv]]=mx
print(END)
for r in m.itertuples():
    cc=DIV[r.Division]; tier=2 if r.Division in("E1","SP2","I2","F2","D2") else 1
    rows.append(dict(date=r.MatchDate,home=r.HomeTeam,away=r.AwayTeam,hcc=cc,acc=cc,hg=int(r.FTHome),ag=int(r.FTAway),comp="DOM" if tier==1 else "DOM2",src="mcsv",
                     helo=r.HomeElo,aelo=r.AwayElo,ohome=r.OddHome,odraw=r.OddDraw,oaway=r.OddAway))
MCSV_CC=set(DIV.values())
for folder,cc in FOLDER.items():
    for f in sorted(glob.glob(f"{FD}/europe/{folder}/*.txt")):
        b=os.path.basename(f)
        if not re.search(r"_[a-z]+1\.txt$",b): continue
        yr=int(b[:4])
        if yr<2021: continue
        rs=parse_txt(f,"DOM",cc)
        if cc in END: rs=[x for x in rs if x["date"]>END[cc]]
        rows+=rs
for f in sorted(glob.glob(f"{FD}/football.json/202[4-6]-2[5-7]/*.json")):
    code=os.path.basename(f).split(".")[0]; lvl=os.path.basename(f).split(".")[1]
    if lvl!="1" or code not in FJ: continue
    cc=FJ[code]
    for x in json.load(open(f))["matches"]:
        sc=x.get("score"); sc=sc if isinstance(sc,dict) else {"ft":sc} if isinstance(sc,list) and len(sc)==2 else {}
        if not sc.get("ft") or (cc in END and x["date"]<=END[cc]): continue
        rows.append(dict(date=x["date"],home=x["team1"],away=x["team2"],hcc=cc,acc=cc,hg=sc["ft"][0],ag=sc["ft"][1],comp="DOM",src="fj"))
COMP={"cl":"UCL","el":"UEL","conf":"UECL","clq":"UCLQ","elq":"UELQ","confq":"UECLQ"}
for f in sorted(glob.glob(f"{FD}/champions-league/20*/*.txt")):
    s=f.split("/")[-2]
    if int(s[:4])<2021: continue
    k=os.path.basename(f)[:-4]
    if k not in COMP: continue
    rows+=parse_txt(f,COMP[k])
for x in euro2627.R:
    if x.get("aet"): continue
    rows.append(x)
df=pd.DataFrame(rows)
# drop duplicate fj/europe rows that coincide with each other for 2026-27
df["key"]=df.date+"|"+df.hcc+"|"+df.home+"|"+df.away
df=df.drop_duplicates("key")
df.to_pickle(str(paths.WORK / "raw.pkl"))
print(len(df)); print(df.comp.value_counts()); print(df.date.max())
