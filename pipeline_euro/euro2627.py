# 2026/27 European results gathered by research agents (UEFA.com, Wikipedia, footballwebpages, ESPN), 22 Oct 2026.
R=[]
def add(stage,date,h,hc,a,ac,hg,ag,comp,aet=False):
    R.append(dict(date=date,home=h,away=a,hcc=hc,acc=ac,hg=hg,ag=ag,comp=comp,src="agent_"+stage,aet=aet))
# UEL MD1
for d,h,hc,a,ac,hg,ag in [
("2026-09-16","Ararat-Armenia","ARM","Sparta Praha","CZE",1,4),("2026-09-16","Omonia","CYP","Celta Vigo","ESP",1,0),
("2026-09-16","AC Milan","ITA","Benfica","POR",0,2),("2026-09-16","Bayer Leverkusen","GER","Celje","SVN",2,0),
("2026-09-16","Hapoel Beer Sheva","ISR","Dinamo Zagreb","CRO",0,0),("2026-09-16","Olympiacos","GRE","Jagiellonia","POL",2,1),
("2026-09-16","Anderlecht","BEL","Lyon","FRA",1,2),("2026-09-16","Sturm Graz","AUT","Rennes","FRA",0,0),
("2026-09-16","Sunderland","ENG","AZ Alkmaar","NED",1,0),("2026-09-17","OFI Crete","GRE","Hoffenheim","GER",2,0),
("2026-09-17","Levski Sofia","BUL","Salzburg","AUT",0,1),("2026-09-17","Besiktas","TUR","Marseille","FRA",4,1),
("2026-09-17","Celtic","SCO","Ferencvaros","HUN",1,3),("2026-09-17","Crystal Palace","ENG","Lech Poznan","POL",4,0),
("2026-09-17","Viktoria Plzen","CZE","Union Saint-Gilloise","BEL",0,3),("2026-09-17","Juventus","ITA","NEC Nijmegen","NED",5,0),
("2026-09-17","Lillestrom","NOR","Torreense","POR",1,2),("2026-09-17","Real Sociedad","ESP","Bournemouth","ENG",1,2)]:
    add("UEL_MD1",d,h,hc,a,ac,hg,ag,"UEL")
for h,hc,a,ac,hg,ag in [("Sparta Praha","CZE","Lillestrom","NOR",1,1),("AZ Alkmaar","NED","Hapoel Beer Sheva","ISR",2,1),
("Salzburg","AUT","AC Milan","ITA",0,4),("Lech Poznan","POL","Bayer Leverkusen","GER",0,4),("Celje","SVN","Omonia","CYP",0,3),
("Lyon","FRA","Crystal Palace","ENG",3,2),("Union Saint-Gilloise","BEL","Real Sociedad","ESP",1,1),("Torreense","POR","Sunderland","ENG",1,2),
("Bournemouth","ENG","Sturm Graz","AUT",3,0),("Ferencvaros","HUN","Viktoria Plzen","CZE",2,1),("Dinamo Zagreb","CRO","Anderlecht","BEL",1,0),
("Jagiellonia","POL","Ararat-Armenia","ARM",3,1),("NEC Nijmegen","NED","Levski Sofia","BUL",1,1),("Marseille","FRA","Olympiacos","GRE",0,1),
("Celta Vigo","ESP","Juventus","ITA",1,2),("Benfica","POR","Celtic","SCO",4,1),("Rennes","FRA","OFI Crete","GRE",2,1),("Hoffenheim","GER","Besiktas","TUR",2,3)]:
    add("UEL_MD2","2026-10-15",h,hc,a,ac,hg,ag,"UEL")
# UEL Q3 and PO (scores as reported; a.e.t. legs flagged and skipped for goals)
for d,h,hc,a,ac,hg,ag,aet in [
("2026-08-04","Larne","NIR","Iberia 1999","GEO",0,0,0),("2026-08-11","Iberia 1999","GEO","Larne","NIR",2,1,1),
("2026-08-04","Shamrock Rovers","IRL","Egnatia","ALB",3,1,0),("2026-08-13","Egnatia","ALB","Shamrock Rovers","IRL",5,1,0),
("2026-08-05","Ferencvaros","HUN","Gornik Zabrze","POL",1,0,0),("2026-08-13","Gornik Zabrze","POL","Ferencvaros","HUN",1,1,0),
("2026-08-06","KuPS","FIN","Universitatea Craiova","ROU",1,1,0),("2026-08-13","Universitatea Craiova","ROU","KuPS","FIN",2,1,0),
("2026-08-06","Lincoln Red Imps","GIB","Omonia","CYP",1,1,0),("2026-08-13","Omonia","CYP","Lincoln Red Imps","GIB",1,0,0),
("2026-08-06","Lech Poznan","POL","KI Klaksvik","FRO",1,0,0),("2026-08-14","KI Klaksvik","FRO","Lech Poznan","POL",0,5,0),
("2026-08-06","Thun","SUI","Vikingur Reykjavik","ISL",3,0,0),("2026-08-13","Vikingur Reykjavik","ISL","Thun","SUI",3,2,0),
("2026-08-06","Jagiellonia","POL","Rangers","SCO",2,1,0),("2026-08-13","Rangers","SCO","Jagiellonia","POL",1,1,0),
("2026-08-06","Maccabi Tel Aviv","ISR","CSKA Sofia","BUL",0,3,0),("2026-08-13","CSKA Sofia","BUL","Maccabi Tel Aviv","ISR",1,3,0),
("2026-08-06","Salzburg","AUT","Pafos","CYP",1,0,0),("2026-08-13","Pafos","CYP","Salzburg","AUT",3,3,0),
("2026-08-06","Hradec Kralove","CZE","Besiktas","TUR",0,1,0),("2026-08-13","Besiktas","TUR","Hradec Kralove","CZE",1,0,0),
("2026-08-06","PAOK","GRE","Anderlecht","BEL",0,1,0),("2026-08-13","Anderlecht","BEL","PAOK","GRE",3,2,0),
("2026-08-06","Benfica","POR","Hearts","SCO",6,1,0),("2026-08-13","Hearts","SCO","Benfica","POR",1,1,0),
("2026-08-20","Kairat","KAZ","Anderlecht","BEL",0,3,0),("2026-08-27","Anderlecht","BEL","Kairat","KAZ",3,0,0),
("2026-08-20","Jagiellonia","POL","Iberia 1999","GEO",4,0,0),("2026-08-27","Iberia 1999","GEO","Jagiellonia","POL",1,2,0),
("2026-08-20","Mjallby","SWE","Salzburg","AUT",0,1,0),("2026-08-27","Salzburg","AUT","Mjallby","SWE",3,0,0),
("2026-08-20","Trabzonspor","TUR","Ferencvaros","HUN",0,1,0),("2026-08-27","Ferencvaros","HUN","Trabzonspor","TUR",4,0,0),
("2026-08-20","Universitatea Craiova","ROU","Ararat-Armenia","ARM",1,1,0),("2026-08-27","Ararat-Armenia","ARM","Universitatea Craiova","ROU",1,0,0),
("2026-08-20","Egnatia","ALB","Lillestrom","NOR",0,0,0),("2026-08-27","Lillestrom","NOR","Egnatia","ALB",2,1,1),
("2026-08-20","Besiktas","TUR","Kauno Zalgiris","LTU",3,0,0),("2026-08-27","Kauno Zalgiris","LTU","Besiktas","TUR",1,0,0),
("2026-08-20","Lech Poznan","POL","Thun","SUI",7,0,0),("2026-08-27","Thun","SUI","Lech Poznan","POL",2,2,0),
("2026-08-20","Sint-Truiden","BEL","Omonia","CYP",1,0,0),("2026-08-27","Omonia","CYP","Sint-Truiden","BEL",4,2,0),
("2026-08-20","Crvena Zvezda","SRB","Viktoria Plzen","CZE",3,0,0),("2026-08-27","Viktoria Plzen","CZE","Crvena Zvezda","SRB",5,1,1),
("2026-08-20","OFI Crete","GRE","CSKA Sofia","BUL",3,0,0),("2026-08-27","CSKA Sofia","BUL","OFI Crete","GRE",0,2,0),
("2026-08-20","Benfica","POR","AGF","DEN",3,1,0),("2026-08-27","AGF","DEN","Benfica","POR",1,3,0)]:
    add("UEL_QPO",d,h,hc,a,ac,hg,ag,"UELQ",bool(aet))
# UECL MD1
for h,hc,a,ac,hg,ag in [("Lugano","SUI","Crvena Zvezda","SRB",3,2),("Hajduk Split","CRO","Ajax","NED",2,1),("Gent","BEL","AGF","DEN",1,0),
("Egnatia","ALB","Midtjylland","DEN",1,1),("KuPS","FIN","Trabzonspor","TUR",2,4),("Mjallby","SWE","Inter Club d'Escaldes","AND",2,0),
("Panathinaikos","GRE","Borac Banja Luka","BIH",2,1),("CSKA Sofia","BUL","Monaco","FRA",1,2),("Riga","LVA","Kairat","KAZ",1,1),
("Universitatea Craiova","ROU","Getafe","ESP",1,1),("Atalanta","ITA","Pafos","CYP",3,1),("Brighton","ENG","Kauno Zalgiris","LTU",4,0),
("FC Copenhagen","DEN","Braga","POR",3,0),("Twente","NED","Thun","SUI",1,0),("Hearts","SCO","Nordsjaelland","DEN",1,1),
("Sint-Truiden","BEL","Iberia 1999","GEO",2,0),("Freiburg","GER","Jablonec","CZE",3,2),("Brann","NOR","Lincoln Red Imps","GIB",2,1)]:
    add("UECL_MD1","2026-10-15",h,hc,a,ac,hg,ag,"UECL")
# UECL play-off (medium confidence, single source); second legs dated 2026-08-27
for h,hc,a,ac,s1,s2,aet2 in [
("Vikingur Reykjavik","ISL","Borac Banja Luka","BIH",(1,3),(3,1),0),("Shamrock Rovers","IRL","KuPS","FIN",(1,1),(1,0),0),
("Drita","KOS","Inter Club d'Escaldes","AND",(2,2),(0,0),1),("KI Klaksvik","FRO","Riga","LVA",(0,0),(2,1),0),
("Lincoln Red Imps","GIB","Larne","NIR",(0,2),(0,3),1),("Motherwell","SCO","Freiburg","GER",(1,3),(4,1),0),
("Gornik Zabrze","POL","Monaco","FRA",(2,3),(4,1),0),("Inter Turku","FIN","FC Copenhagen","DEN",(0,0),(4,1),0),
("Hearts","SCO","Rapid Wien","AUT",(2,2),(2,2),1),("Tromso","NOR","Brighton","ENG",(0,0),(4,0),0),
("Hajduk Split","CRO","Rakow","POL",(2,2),(2,3),1),("Panathinaikos","GRE","Hradec Kralove","CZE",(2,2),(1,2),1),
("Gent","BEL","Hibernian","SCO",(0,0),(2,3),0),("PAOK","GRE","Brann","NOR",(1,1),(3,2),0),
("Atalanta","ITA","Hapoel Tel Aviv","ISR",(0,0),(0,1),0),("Midtjylland","DEN","Rijeka","CRO",(2,0),(1,4),0),
("Rangers","SCO","Jablonec","CZE",(1,0),(1,0),1),("Nordsjaelland","DEN","St. Gallen","SUI",(1,0),(2,3),0),
("Dinamo City","ALB","Pafos","CYP",(1,1),(4,2),1),("Sion","SUI","Ajax","NED",(2,4),(5,3),0),
("Braga","POR","Austria Wien","AUT",(2,0),(0,0),0),("Twente","NED","Qarabag","AZE",(0,1),(1,4),1),
("Getafe","ESP","Partizan","SRB",(3,1),(2,1),0),("Lugano","SUI","Maccabi Tel Aviv","ISR",(2,1),(1,1),0)]:
    add("UECL_PO","2026-08-20",h,hc,a,ac,s1[0],s1[1],"UECLQ")
    add("UECL_PO","2026-08-27",a,ac,h,hc,s2[0],s2[1],"UECLQ",bool(aet2))
# UCL MD3 (20-21 Oct) verified earlier in this session
for d,h,hc,a,ac,hg,ag in [("2026-10-20","Sabah","AZE","Dortmund","GER",1,2),("2026-10-20","Fenerbahce","TUR","Slavia Praha","CZE",2,2),
("2026-10-20","Paris Saint-Germain","FRA","Barcelona","ESP",4,2),("2026-10-20","Porto","POR","PSV","NED",0,1),("2026-10-20","Napoli","ITA","Bodo/Glimt","NOR",4,3),
("2026-10-20","Roma","ITA","Slovan Bratislava","SVK",4,0),("2026-10-20","Liverpool","ENG","Villarreal","ESP",4,3),("2026-10-20","Stuttgart","GER","Atletico Madrid","ESP",1,1),
("2026-10-20","Manchester City","ENG","AEK Athens","GRE",5,1),("2026-10-21","Como","ITA","Manchester United","ENG",4,1),("2026-10-21","Lille","FRA","Galatasaray","TUR",2,4),
("2026-10-21","Real Betis","ESP","Feyenoord","NED",1,0),("2026-10-21","Aston Villa","ENG","Viking","NOR",3,1),("2026-10-21","Club Brugge","BEL","Lens","FRA",3,0),
("2026-10-21","Bayern Munich","GER","Arsenal","ENG",2,2),("2026-10-21","Inter","ITA","Shakhtar Donetsk","UKR",1,0),("2026-10-21","Sporting CP","POR","LASK","AUT",2,3),
("2026-10-21","Real Madrid","ESP","RB Leipzig","GER",4,1),("2026-10-21","Levante","ESP","Athletic Bilbao","ESP",3,1)]:
    add("UCL_MD3",d,h,hc,a,ac,hg,ag,"UCL" if hc!=ac else "DOM")
FIX=[]
def fx(comp,ko,h,hc,a,ac,rnd): FIX.append(dict(comp=comp,kickoff=ko,home=h,hcc=hc,away=a,acc=ac,round=rnd))
for t,h,hc,a,ac in [("16:45","Ararat-Armenia","ARM","AZ Alkmaar","NED"),("16:45","Ferencvaros","HUN","Torreense","POR"),("16:45","Dinamo Zagreb","CRO","NEC Nijmegen","NED"),
("16:45","Juventus","ITA","Rennes","FRA"),("16:45","Lech Poznan","POL","Sunderland","ENG"),("16:45","OFI Crete","GRE","Bayer Leverkusen","GER"),
("16:45","Union Saint-Gilloise","BEL","Hapoel Beer Sheva","ISR"),("16:45","Sturm Graz","AUT","Marseille","FRA"),("19:00","Bournemouth","ENG","AC Milan","ITA"),
("19:00","Besiktas","TUR","Crystal Palace","ENG"),("19:00","Celtic","SCO","Celta Vigo","ESP"),("19:00","Viktoria Plzen","CZE","Levski Sofia","BUL"),
("19:00","Jagiellonia","POL","Anderlecht","BEL"),("19:00","Lillestrom","NOR","Real Sociedad","ESP"),("19:00","Celje","SVN","Salzburg","AUT"),
("19:00","Olympiacos","GRE","Sparta Praha","CZE"),("19:00","Omonia","CYP","Benfica","POR"),("19:00","Hoffenheim","GER","Lyon","FRA")]:
    fx("UEL","2026-10-22T"+t+"Z",h,hc,a,ac,"League phase, matchday 3")
for t,h,hc,a,ac in [("14:30","Kairat","KAZ","Panathinaikos","GRE"),("16:45","Iberia 1999","GEO","Mjallby","SWE"),("16:45","Nordsjaelland","DEN","CSKA Sofia","BUL"),
("16:45","Crvena Zvezda","SRB","FC Copenhagen","DEN"),("16:45","Jablonec","CZE","Brighton","ENG"),("16:45","Kauno Zalgiris","LTU","Brann","NOR"),
("16:45","Getafe","ESP","Lugano","SUI"),("16:45","Inter Club d'Escaldes","AND","Universitatea Craiova","ROU"),("16:45","Pafos","CYP","Riga","LVA"),
("16:45","Trabzonspor","TUR","Hearts","SCO"),("19:00","Ajax","NED","Atalanta","ITA"),("19:00","AGF","DEN","Egnatia","ALB"),("19:00","Monaco","FRA","Freiburg","GER"),
("19:00","Midtjylland","DEN","Sint-Truiden","BEL"),("19:00","Thun","SUI","Hajduk Split","CRO"),("19:00","Borac Banja Luka","BIH","KuPS","FIN"),
("19:00","Lincoln Red Imps","GIB","Twente","NED"),("19:00","Braga","POR","Gent","BEL")]:
    fx("UECL","2026-10-22T"+t+"Z",h,hc,a,ac,"League phase, matchday 2")
