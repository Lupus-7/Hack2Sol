import datetime
import random
 
class Produktionsauftrag:
    def __init__(self, auftragsnummer, produkt, bedarfstermin, bedarfsmenge, produktfamilie, ruestzeit_produktfamilie=0, verkaufspreis=1.0):
        self.auftragsnummer = auftragsnummer
        self.produkt = produkt
        self.bedarfstermin = bedarfstermin  # Datumsobjekt
        self.bedarfsmenge = bedarfsmenge
        self.produktfamilie = produktfamilie
        self.ruestzeit_produktfamilie = ruestzeit_produktfamilie  # Stunden (Rüstzeit bei Wechsel der Produktfamilie)
        self.verkaufspreis = verkaufspreis  # Preis pro Einheit
        self.fertigungsdatum = None
 
    def __repr__(self):
        return f"Auftrag(Nr={self.auftragsnummer}, Produkt={self.produkt}, Termin={self.bedarfstermin.strftime('%Y-%m-%d')}, Menge={self.bedarfsmenge}, Familie={self.produktfamilie})"
 
 
def berechne_bewertung(produktionsreihenfolge, auftraege, lagerkosten_pro_einheit_pro_tag,
                       maximale_produktionskapazitaet_pro_tag,
                       w1=0.5, w2=0.3, w3=0.2, planungsperiode_tage=28):
 
    umsatz, lagerkosten, produzierte_gesamtmenge = 0, 0, 0
    ruestzeiten_gesamt = 0
    lagerbestand = {}
    tagesumsatz = {}
    startdatum = datetime.datetime(2025, 11, 25)
    enddatum = start_datum + datetime.timedelta(days=planungsperiode_tage)
    produktionsdatum = startdatum
    letzte_produktfamilie = None
    gesamte_produktionszeit_in_stunden = 0
    bisher_produzierte_menge = 0
    ende_aktueller_auftrag = startdatum
 
 
    # Gehe die Produktionsreihenfolge (=Auftragsslotnummern) der Reihe nach durch
    for idx, auftragsnummer in enumerate(produktionsreihenfolge):
        auftrag = auftraege[auftragsnummer]
        if (ende_aktueller_auftrag > datetime.datetime.combine(enddatum, datetime.datetime.min.time())):
           # print(f"Anzahl der ausgeführten Aufträge: {idx}")
            break
        # Rüstzeit zwischen wechselnden Produktfamilien
        if letzte_produktfamilie != auftrag.produktfamilie and letzte_produktfamilie is not None:
            ruestzeit = auftrag.ruestzeit_produktfamilie
            ruestzeiten_gesamt += ruestzeit
            produktionsdatum += datetime.timedelta(hours=ruestzeit)
            gesamte_produktionszeit_in_stunden += ruestzeit
            # Falls durch die Rüstzeit ein Tag "überschritten" wird, erhöhe ggf. Tag
        else:
            ruestzeit = 0
 
        letzte_produktfamilie = auftrag.produktfamilie
 
        # Solange noch bedarfsmenge offen und Zeit übrig
        heutiges_datum = produktionsdatum.date()
        tagesumsatz.setdefault(heutiges_datum, 0)
        summe_aller_auftragsmengen = sum(auftrag.bedarfsmenge for auftrag in auftraege.values())
        tagesproduktion = min(summe_aller_auftragsmengen - bisher_produzierte_menge, maximale_produktionskapazitaet_pro_tag)
        bisher_produzierte_menge += auftrag.bedarfsmenge
        produzierte_gesamtmenge += auftrag.bedarfsmenge
 
        # Umsatz nur, wenn pünktlich fertig
        if auftrag.bedarfsmenge <= 0 and produktionsdatum.date() <= auftrag.bedarfstermin:
            umsatz += auftrag.verkaufspreis * tagesproduktion
            tagesumsatz[heutiges_datum] += auftrag.verkaufspreis * auftrag.bedarfsmenge
 
        # Lagerbestand aktualisieren (TODO: Lieferdatum berücksichtigen)
        lagerbestand[auftrag.produkt] = lagerbestand.get(auftrag.produkt, 0) + auftrag.bedarfsmenge
 
        # Lagerkosten für heute neu verrechnen
        for produkt, menge in lagerbestand.items():
            # Tage bis zum Bedarfsdatum:
            lagerdauer = max(0, (auftrag.bedarfstermin - heutiges_datum).days)
            lagerkosten += ((auftrag.verkaufspreis*0.16)/365) * menge * lagerdauer
        # Zeit fortschreiben
        produktionsdatum += datetime.timedelta(days=1)
        gesamte_produktionszeit_in_stunden += 24
 
        laufzeit_min, _ = berechne_auftragslaufzeit(auftrag, output_pro_minute=69.444444) # TODO: output_pro_minute aus masterdata nehmen
        ende_aktueller_auftrag += datetime.timedelta(minutes=laufzeit_min + (ruestzeit * 60))
        auftrag.fertigungsdatum = ende_aktueller_auftrag
    wochen_ergebnisse = []
    for woche in range(4):
        # Wochenstart und -ende berechnen
        wochenstart = start_datum + datetime.timedelta(days=7*woche)
        wochenstart = datetime.datetime.combine(wochenstart, datetime.datetime.min.time())
        wochenende = start_datum + datetime.timedelta(days=7*(woche+1))
        wochenende = datetime.datetime.combine(wochenende, datetime.datetime.min.time())
 
 
        # Filter: Aufträge, deren Bedarfstermin und Fertigungsdatum beide in der aktuellen Woche liegen
        auftraege_in_woche = [
            auftrag for auftrag in auftraege.values()
            if auftrag.fertigungsdatum is not None and wochenstart < datetime.datetime.combine(auftrag.bedarfstermin, datetime.datetime.min.time())  <= wochenende and wochenstart < auftrag.fertigungsdatum <= wochenende
        ]
        umsatz_woche = sum(
            auftrag.bedarfsmenge * auftrag.verkaufspreis for auftrag in auftraege_in_woche
        )
        wochen_ergebnisse.append(umsatz_woche)
 
    # Ergebnisse:
    umsatz_woche_1, umsatz_woche_2, umsatz_woche_3, umsatz_woche_4 = wochen_ergebnisse
    #print(umsatz_woche_1, umsatz_woche_2, umsatz_woche_3, umsatz_woche_4) # hier ist noch auf tatsächlich auszuliefernde Kundenaufträge aufzudröseln# und die Verfügbarkeit der Produkte zu analysieren
 
    lagerkosten = sum(
           max(0, auftrag.bedarfsmenge * auftrag.verkaufspreis *int((datetime.datetime.combine(auftrag.bedarfstermin, datetime.datetime.min.time()) - auftrag.fertigungsdatum).days))
           for auftrag in auftraege.values()
        if auftrag.fertigungsdatum
        )*0.16/365
 
    # OEE-Berechnung
    tatsaechlich_verfuegbare_produktionszeit = planungsperiode_tage * 24 - ruestzeiten_gesamt
    maximale_moegliche_produktion = maximale_produktionskapazitaet_pro_tag * planungsperiode_tage
    if maximale_moegliche_produktion > 0:
        oee = (produzierte_gesamtmenge / maximale_moegliche_produktion) * 100
    else:
        oee = 0
    oee = min(100, oee)
 
    #Berechnung und Gewichtung des Umsatzes
    umsatz = umsatz_woche_1*0.75 + umsatz_woche_2*0.5 + umsatz_woche_3*0.25 + umsatz_woche_4*0.10
    oee_factor=None
    if oee > 80:
        oee_factor = 1.2
    elif oee > 60:
        oee_factor = 0.75
    elif oee > 40:
        oee_factor = 0.5
    else:
        oee_factor = 0.25
 
    # Bewertung
    bewertung = w1 * umsatz + w2 * lagerkosten + w3 * oee_factor
 
    return bewertung, umsatz, lagerkosten, oee, ruestzeiten_gesamt
 
def bewerte_reihenfolge(reihenfolge, auftraege, original_bedarfsmengen, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, w1, w2, w3):
    """Vereinfachte Bewertungsfunktion für den genetischen Algorithmus."""
    # Stelle die ursprüngliche Bedarfsmenge wieder her, bevor die Bewertung durchgeführt wird
    # for auftragsnummer, auftrag in auftraege.items():
    #     auftrag.bedarfsmenge = original_bedarfsmengen[auftragsnummer]
    auftraege_kopie = {}
    for auftragsnummer in auftraege:
      auftrag = auftraege[auftragsnummer]
      auftraege_kopie[auftragsnummer] = Produktionsauftrag(auftrag.auftragsnummer, auftrag.produkt, auftrag.bedarfstermin, auftrag.bedarfsmenge, auftrag.produktfamilie, auftrag.ruestzeit_produktfamilie, auftrag.verkaufspreis)
 
    bewertung, umsatz, lagerkosten, oee, ruestzeiten_gesamt = berechne_bewertung(
        reihenfolge, auftraege_kopie, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, w1=0.7, w2=0.1, w3=0.2
    )
 
    return bewertung
 
def generiere_auftraege(anzahl_auftraege, start_datum, produkte, produktfamilien, min_bedarfsmenge=50, max_bedarfsmenge=50000):
    """Generiert eine Liste von zufälligen Produktionsaufträgen mit zufälliger Bedarfsmenge je Auftrag."""
    auftraege_daten = []
    for i in range(anzahl_auftraege):
        produkt = random.choice(produkte)
        produktfamilie = random.choice(produktfamilien)
        bedarfstermin = start_datum + datetime.timedelta(days = random.randint(0, 60))
        bedarfsmenge = random.randint(100000, 300000)
        ruestzeit_produktfamilie = random.randint(1, 5)
        verkaufspreis = random.randint(8, 25)
        auftragsnummer = f"A{i+1}"
 
        auftraege_daten.append({
            "auftragsnummer": auftragsnummer,
            "produkt": produkt,
            "bedarfstermin": bedarfstermin,
            "bedarfsmenge": bedarfsmenge,
            "produktfamilie": produktfamilie,
            "ruestzeit_produktfamilie": ruestzeit_produktfamilie,
            "verkaufspreis": verkaufspreis,
        })
 
    return auftraege_daten
 
 
def generiere_population(auftraege, populationsgroesse):
    """Generiert eine Population von Produktionsreihenfolgen."""
    auftragsnummern = list(auftraege.keys())
    population = []
    for _ in range(populationsgroesse):
        reihenfolge = auftragsnummern[:]
        random.shuffle(reihenfolge)
        population.append(reihenfolge)
    return population
 
def selektion(population, bewertungen, anzahl_eltern):
    """Selektiert die besten Eltern aus der Population."""
    eltern = []
    bewertungen_mit_index = sorted(enumerate(bewertungen), key=lambda x: x[1], reverse=True) #Sortiere nach Bewertung (absteigend)
    for i in range(anzahl_eltern):
        eltern.append(population[bewertungen_mit_index[i][0]])  #Nimm die Auftragsreihenfolge, die zu der besten Bewertung gehört
    return eltern
 
def kreuzung(eltern):
    """Führt eine Kreuzung zwischen zwei Eltern durch, um ein Kind zu erzeugen."""
    elternteil1 = random.choice(eltern)
    elternteil2 = random.choice(eltern)
    schnittpunkt = random.randint(1, len(elternteil1) - 1)
    kind = elternteil1[:schnittpunkt] + [item for item in elternteil2 if item not in elternteil1[:schnittpunkt]] #Erzeuge Kind
    return kind
 
def mutation(reihenfolge, mutationsrate):
    """Führt eine Mutation in einer Produktionsreihenfolge durch."""
    for i in range(len(reihenfolge)):
        if random.random() < mutationsrate:
            index1 = random.randint(0, len(reihenfolge) - 1)
            index2 = random.randint(0, len(reihenfolge) - 1)
            reihenfolge[index1], reihenfolge[index2] = reihenfolge[index2], reihenfolge[index1]  #Tausche 2 zufällige Elemente
    return reihenfolge
 
 
def genetischer_algorithmus(auftraege, plagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, original_bedarfsmengen, populationsgroesse=100, anzahl_generationen=50, anzahl_eltern=15, mutationsrate=0.05, w1=0.7, w2=0.1, w3=0.2):
    """Führt den genetischen Algorithmus durch."""
 
    population = generiere_population(auftraege, populationsgroesse)
 
    for generation in range(anzahl_generationen):
        bewertungen = [bewerte_reihenfolge(reihenfolge, auftraege, original_bedarfsmengen, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, w1, w2, w3) for reihenfolge in population]
        eltern = selektion(population, bewertungen, anzahl_eltern)
        neue_population = eltern[:]  # Die Eltern bleiben erhalten
        print(generation)
        print(str(max(bewertungen)))
        print('TEST GENERATION')
        while len(neue_population) < populationsgroesse:
            kind = kreuzung(eltern)
            kind = mutation(kind, mutationsrate)
            neue_population.append(kind)
 
        population = neue_population
 
    # Finde die beste Lösung in der letzten Population
    bewertungen = [bewerte_reihenfolge(reihenfolge, auftraege, original_bedarfsmengen, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, w1, w2, w3) for reihenfolge in population]
    beste_index = bewertungen.index(max(bewertungen))
    beste_reihenfolge = population[beste_index]
 
    return beste_reihenfolge
 
 
# Beispielanwendung
if __name__ == '__main__':
    # Parameter definieren
    anzahl_auftraege = 200  # Hier die Anzahl der Aufträge festlegen
    start_datum = datetime.date(2025, 11, 25)
    produkte = ["ProduktA", "ProduktB", "ProduktC", "ProduktD", "ProduktE", "ProduktF", "ProduktG", "ProduktH", "ProduktI", "ProduktJ", "ProduktK", "ProduktL"]
    produktfamilien = ["Familie1", "Familie2", "Familie3", "Familie4", "Familie5", "Familie6", "Familie7", "Familie8", "Familie9", "Familie10", "Familie11", "Familie12"]
    gesamte_bedarfsmenge = 1000000 #Gesamte Bedarfsmenge für 4 Wochen
 
    # Aufträge generieren
    auftraege_daten = generiere_auftraege(anzahl_auftraege, start_datum, produkte, produktfamilien, gesamte_bedarfsmenge)
 
    auftraege = {}
    for data in auftraege_daten: #Erstelle Aufträge-Objekte, aber kopiere die ursprüngliche Bedarfsmenge
         auftrag = Produktionsauftrag(**data)
         auftraege[data["auftragsnummer"]] = auftrag
 
 
 
    lagerkosten_pro_einheit_pro_tag = {
        "ProduktA": 0.01, #Reduziere die Lagerkosten
        "ProduktB": 0.015,
        "ProduktC": 0.02,
        "ProduktD": 0.012,
        "ProduktE": 0.008,
        "ProduktF": 0.018,
        "ProduktG": 0.022,
        "ProduktH": 0.25,
        "ProduktI": 0.011,
        "ProduktJ": 0.028,
        "ProduktK": 0.014,
        "ProduktL": 0.03
    }
 
 
# Initialisiere ein Dictionary für die Aufträge
 
    maximale_produktionskapazitaet_pro_tag = 100000 #Stück
    output_pro_minute = maximale_produktionskapazitaet_pro_tag / (24 * 60)
    print(f"Output pro Minute: {output_pro_minute:.2f} Stück/min")
 
    def berechne_auftragslaufzeit(auftrag, output_pro_minute):
          laufzeit_min = auftrag.bedarfsmenge / output_pro_minute
          laufzeit_std = laufzeit_min / 60
          return laufzeit_min, laufzeit_std
 
    output_pro_minute = maximale_produktionskapazitaet_pro_tag / 1440
    for auftragsnummer, auftrag in auftraege.items():
        laufzeit_min, laufzeit_std = berechne_auftragslaufzeit(auftrag, output_pro_minute)
        print(f"Auftrag {auftragsnummer}: Laufzeit = {laufzeit_min:.2f} Minuten = {laufzeit_std:.2f} Stunden")
 
 
    def berechne_summe_auftragslaufzeiten(auftraege, output_pro_minute):
        summe_laufzeit_min = 0
        for auftragsnummer, auftrag in auftraege.items():
            laufzeit_min, _ = berechne_auftragslaufzeit(auftrag, output_pro_minute)
            summe_laufzeit_min += laufzeit_min
        summe_laufzeit_std = summe_laufzeit_min / 60
        print(summe_laufzeit_std)
        return summe_laufzeit_min, summe_laufzeit_std
    berechne_summe_auftragslaufzeiten(auftraege, output_pro_minute)
 
    # Speichere die ursprünglichen Bedarfsmengen
    original_bedarfsmengen = {auftragsnummer: auftrag.bedarfsmenge for auftragsnummer, auftrag in auftraege.items()}
 
    # Verwende den genetischen Algorithmus
    beste_reihenfolge = genetischer_algorithmus(auftraege, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, original_bedarfsmengen)
    print(f"Beste Reihenfolge (Genetischer Algorithmus): {beste_reihenfolge}")
 
    # Bewerte die beste Reihenfolge vom genetischen Algorithmus
    #WICHTIG: Erstelle Kopien der Aufträge, damit die Bedarfsmenge nicht verändert wird
    auftraege_kopie = {}
    for auftragsnummer in auftraege:
      auftrag = auftraege[auftragsnummer]
      auftraege_kopie[auftragsnummer] = Produktionsauftrag(auftrag.auftragsnummer, auftrag.produkt, auftrag.bedarfstermin, auftrag.bedarfsmenge, auftrag.produktfamilie, auftrag.ruestzeit_produktfamilie, auftrag.verkaufspreis)
 
    bewertung, umsatz, lagerkosten, oee, ruestzeiten_gesamt = berechne_bewertung(
        beste_reihenfolge, auftraege_kopie, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, w1=0.7, w2=0.1, w3=0.2
    )
 
    print(f" Bewertung (Genetischer Algorithmus): {bewertung:.2f}")
    print(f" Umsatz (Genetischer Algorithmus): {umsatz:.2f}")
    print(f" Lagerkosten (Genetischer Algorithmus): {lagerkosten:.2f}")
    print(f" OEE (Genetischer Algorithmus): {oee:.2f}%")
    print(f" Gesamte Rüstzeiten (Genetischer Algorithmus): {ruestzeiten_gesamt:.2f} Stunden")
    #print(f" Gesamte Bedarfsmenge: {gesamte_bedarfsmenge}")
 
    bewertung, umsatz, lagerkosten, oee, ruestzeiten_gesamt = berechne_bewertung(
        auftraege.keys(), auftraege_kopie, lagerkosten_pro_einheit_pro_tag, maximale_produktionskapazitaet_pro_tag, w1=0.7, w2=0.1, w3=0.2
    )
 
    print(f" Bewertung (Startreihenfolge): {bewertung:.2f}")
    print(f" Umsatz (Startreihenfolge): {umsatz:.2f}")
    print(f" Lagerkosten (Startreihenfolge): {lagerkosten:.2f}")
    print(f" OEE (Startreihenfolge): {oee:.2f}%")
    print(f" Gesamte Rüstzeiten (Startreihenfolge): {ruestzeiten_gesamt:.2f} Stunden")