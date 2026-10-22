import re, unicodedata, difflib, collections
STOP=set("fc afc cf sc sk fk nk gnk hnk kks ks ac as rc rcd sl ssc rsc tsg kaa krc kv k sv bk if aif ik il cd ud pfc tc jk club calcio de del football futbol futebol cp sad sk. vv fk. ofi? 1899 1900 1904 1907 1909 1910 1913 1919 1920 1922 1926 1928 1931 1937 1948 1961 04 05 07 09 kf sfc bv vfb vfl tsv ogc osc us ss as. royale r spvgg sco sv. ca hsk hk s.a.d. mfk ofk fcsb oss".split())
ALIAS={  # normalized -> normalized canonical (global, applied before country clustering)
 "man united":"manchester united","man utd":"manchester united","man city":"manchester city","nottm forest":"nottingham forest","nott m forest":"nottingham forest",
 "wolves":"wolverhampton wanderers","spurs":"tottenham hotspur","tottenham":"tottenham hotspur","newcastle":"newcastle united","west ham":"west ham united","brighton":"brighton hove albion",
 "brighton and hove albion":"brighton hove albion","leeds":"leeds united","leicester":"leicester city","sheffield united":"sheffield united","sheff utd":"sheffield united","bournemouth":"bournemouth",
 "palace":"crystal palace","sunderland":"sunderland","ipswich":"ipswich town","luton":"luton town","norwich":"norwich city","west brom":"west bromwich albion","stoke":"stoke city","hull":"hull city","coventry":"coventry city",
 "ath madrid":"atletico madrid","atletico":"atletico madrid","club atletico madrid":"atletico madrid","ath bilbao":"athletic bilbao","athletic":"athletic bilbao","athletic club":"athletic bilbao","betis":"real betis","sociedad":"real sociedad",
 "celta":"celta vigo","espanol":"espanyol","vallecano":"rayo vallecano","rayo":"rayo vallecano","real madrid":"real madrid","barcelona":"barcelona","sevilla":"sevilla","alaves":"alaves","valladolid":"valladolid",
 "inter":"internazionale","inter milan":"internazionale","milan":"milan","ac milan":"milan","roma":"roma","as roma":"roma","lazio roma":"lazio","napoli":"napoli","juventus":"juventus","atalanta":"atalanta","verona":"hellas verona",
 "paris sg":"paris saint germain","psg":"paris saint germain","paris saint germain":"paris saint germain","marseille":"marseille","olympique marseille":"marseille","olympique de marseille":"marseille","lyon":"lyon","olympique lyonnais":"lyon",
 "st etienne":"saint etienne","rennes":"rennes","stade rennais":"rennes","monaco":"monaco","nice":"nice","lille":"lille","lens":"lens","brest":"brest","stade brestois 29":"brest",
 "bayern munich":"bayern munchen","bayern":"bayern munchen","dortmund":"borussia dortmund","leverkusen":"bayer leverkusen","bayer 04 leverkusen":"bayer leverkusen","m gladbach":"borussia monchengladbach","ein frankfurt":"eintracht frankfurt",
 "hoffenheim":"hoffenheim","1899 hoffenheim":"hoffenheim","freiburg":"freiburg","stuttgart":"stuttgart","rb leipzig":"rb leipzig","leipzig":"rb leipzig","union berlin":"union berlin","mainz":"mainz","wolfsburg":"wolfsburg",
 "psv":"psv eindhoven","psv eindhoven":"psv eindhoven","az alkmaar":"az","alkmaar":"az","az":"az","feyenoord rotterdam":"feyenoord","ajax amsterdam":"ajax","ajax":"ajax","nijmegen":"nec nijmegen","nec":"nec nijmegen","nec nijmegen":"nec nijmegen","twente":"twente","twente enschede":"twente",
 "sp lisbon":"sporting","sporting lisbon":"sporting","sporting cp":"sporting","sporting clube de portugal":"sporting","benfica":"benfica","porto":"porto","sp braga":"braga","sporting braga":"braga","braga":"braga","guimaraes":"vitoria guimaraes","torreense":"torreense","scu torreense":"torreense",
 "besiktas":"besiktas","besiktas jk":"besiktas","fenerbahce":"fenerbahce","galatasaray":"galatasaray","trabzonspor":"trabzonspor","basaksehir":"istanbul basaksehir",
 "olympiakos":"olympiacos","olympiakos piraeus":"olympiacos","olympiacos piraeus":"olympiacos","olympiacos":"olympiacos","paok":"paok","paok saloniki":"paok","paok thessaloniki":"paok","aek":"aek athens","aek athens":"aek athens","panathinaikos":"panathinaikos","ofi crete":"ofi","ofi":"ofi","ofi kritis":"ofi",
 "celtic":"celtic","rangers":"rangers","hearts":"hearts","heart of midlothian":"hearts","hibernian":"hibernian","hibs":"hibernian","motherwell":"motherwell",
 "anderlecht":"anderlecht","club brugge":"club brugge","brugge":"club brugge","club brugge kv":"club brugge","gent":"gent","st truiden":"sint truiden","st. truiden":"sint truiden","sint truidense":"sint truiden","sint truidense vv":"sint truiden","k sint truidense":"sint truiden","union saint gilloise":"union saint gilloise","st gilloise":"union saint gilloise","royale union saint gilloise":"union saint gilloise","union sg":"union saint gilloise","union st gilloise":"union saint gilloise",
 "salzburg":"salzburg","rb salzburg":"salzburg","red bull salzburg":"salzburg","sturm graz":"sturm graz","rapid wien":"rapid wien","rapid vienna":"rapid wien","austria wien":"austria wien","austria vienna":"austria wien","lask":"lask","lask linz":"lask",
 "fc copenhagen":"kobenhavn","copenhagen":"kobenhavn","kobenhavn":"kobenhavn","fc kobenhavn":"kobenhavn","midtjylland":"midtjylland","nordsjaelland":"nordsjaelland","agf":"agf","aarhus":"agf","agf aarhus":"agf","aarhus gymnastikforening":"agf","aarhus gymnastikforening agf":"agf",
 "lillestrom":"lillestrom","lillestrom sk":"lillestrom","brann":"brann","sk brann":"brann","bodo glimt":"bodo glimt","bodoe glimt":"bodo glimt","tromso":"tromso","viking":"viking","molde":"molde","rosenborg":"rosenborg",
 "mjallby":"mjallby","mjallby aif":"mjallby","malmo ff":"malmo","malmo":"malmo","elfsborg":"elfsborg","hacken":"hacken",
 "lugano":"lugano","thun":"thun","basel":"basel","young boys":"young boys","servette":"servette","st gallen":"st gallen","st. gallen":"st gallen","sion":"sion",
 "lech poznan":"lech poznan","jagiellonia":"jagiellonia bialystok","jagiellonia bialystok":"jagiellonia bialystok","legia":"legia warszawa","legia warsaw":"legia warszawa","rakow":"rakow czestochowa","rakow czestochowa":"rakow czestochowa","gornik zabrze":"gornik zabrze",
 "univ craiova":"universitatea craiova","u craiova":"universitatea craiova","universitatea craiova":"universitatea craiova","cs universitatea craiova":"universitatea craiova",
 "kups":"kups","kuopion palloseura":"kups","kups kuopio":"kups","inter turku":"inter turku","hjk":"hjk","hjk helsinki":"hjk",
 "shamrock rovers":"shamrock rovers","dinamo zagreb":"dinamo zagreb","hajduk split":"hajduk split","rijeka":"rijeka","crvena zvezda":"crvena zvezda","red star belgrade":"crvena zvezda","crvena zvezda red star belgrade":"crvena zvezda","fk crvena zvezda":"crvena zvezda","partizan":"partizan","partizan belgrade":"partizan",
 "viktoria plzen":"viktoria plzen","plzen":"viktoria plzen","sparta praha":"sparta praha","sparta prague":"sparta praha","slavia praha":"slavia praha","slavia prague":"slavia praha","jablonec":"jablonec","hradec kralove":"hradec kralove",
 "ferencvaros":"ferencvaros","ferencvarosi":"ferencvaros","ferencvarosi tc":"ferencvaros","celje":"celje","levski sofia":"levski sofia","cska sofia":"cska sofia","ludogorets":"ludogorets","ludogorets razgrad":"ludogorets",
 "omonia":"omonia","omonia nicosia":"omonia","ac omonia":"omonia","pafos":"pafos","apoel":"apoel","apoel nicosia":"apoel",
 "hapoel beer sheva":"hapoel beer sheva","hapoel be er sheva":"hapoel beer sheva","hapoel beersheva":"hapoel beer sheva","maccabi tel aviv":"maccabi tel aviv","maccabi tel aviv fc":"maccabi tel aviv","hapoel tel aviv":"hapoel tel aviv",
 "ararat armenia":"ararat armenia","kairat":"kairat","kairat almaty":"kairat","iberia 1999":"iberia 1999","iberia 1999 tbilisi":"iberia 1999","egnatia":"egnatia","egnatia rrogozhine":"egnatia",
 "inter club d escaldes":"inter escaldes","inter escaldes":"inter escaldes","inter club escaldes":"inter escaldes","riga":"riga","riga fc":"riga","kauno zalgiris":"kauno zalgiris","borac banja luka":"borac banja luka","lincoln red imps":"lincoln red imps","lincoln":"lincoln red imps",
 "getafe":"getafe","qarabag":"qarabag","qarabag fk":"qarabag","vikingur reykjavik":"vikingur reykjavik","ki klaksvik":"ki klaksvik","klaksvik":"ki klaksvik","larne":"larne","drita":"drita","dinamo city":"dinamo city",
}
def norm(s):
    s=unicodedata.normalize("NFKD",str(s)); s="".join(c for c in s if not unicodedata.combining(c))
    s=s.lower().replace("&"," and ").replace("ø","o").replace("æ","ae").replace("ß","ss").replace("ł","l").replace("đ","d").replace("ı","i")
    s=re.sub(r"[^a-z0-9 ]"," ",s); s=re.sub(r"\s+"," ",s).strip()
    if s in ALIAS: return ALIAS[s]
    t=[w for w in s.split() if w not in STOP]
    s2=" ".join(t) if t else s
    return ALIAS.get(s2,s2)
def resolve(df):
    # cluster names per country: exact norm, then token-subset / fuzzy merge toward the most frequent form
    cnt=collections.Counter()
    for side in("home","away"):
        for n,c in zip(df[side],df[side[0]+"cc"]): cnt[(c,norm(n))]+=1
    bycc=collections.defaultdict(list)
    for (c,n),k in cnt.items(): bycc[c].append((k,n))
    canon={}
    for c,lst in bycc.items():
        lst.sort(reverse=True); heads=[]
        for k,n in lst:
            tgt=None; ts=set(n.split())
            LOCK=set(ALIAS.values())
            for h in heads:
                if n!=h and (n in LOCK and h in LOCK): continue
                hs=set(h.split())
                if n==h or (len(n)>=4 and (ts<=hs or hs<=ts) and min(len(ts),len(hs))>=1 and (len(ts&hs)>=1) and max(len(x) for x in ts&hs)>=4) or difflib.SequenceMatcher(None,n,h).ratio()>=0.9:
                    tgt=h; break
            if tgt is None: heads.append(n); tgt=n
            canon[(c,n)]=tgt
    return lambda name,cc: cc+":"+canon.get((cc,norm(name)),norm(name))
