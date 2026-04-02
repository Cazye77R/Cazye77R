"""Vokabular und Templates fuer den Aenderungsmitteilungs-Generator."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Personennamen
# ---------------------------------------------------------------------------
VORNAMEN: list[str] = [
    "Andreas", "Barbara", "Christian", "Daniela", "Erik", "Franziska",
    "Georg", "Hannah", "Ingo", "Julia", "Klaus", "Laura", "Markus",
    "Nicole", "Oliver", "Petra", "Ralf", "Sabine", "Thomas", "Ursula",
    "Volker", "Werner", "Yvonne", "Axel", "Birgit", "Carsten", "Doris",
    "Eberhard", "Gisela", "Heinrich", "Ingrid", "Juergen", "Katharina",
    "Lothar", "Monika", "Norbert", "Regina", "Stefan", "Ulrike", "Bernd",
]

NACHNAMEN: list[str] = [
    "Bauer", "Beck", "Braun", "Fischer", "Frank", "Friedrich", "Fuchs",
    "Hartmann", "Hess", "Hoffmann", "Huber", "Jung", "Klein", "Koch",
    "Koehler", "Krause", "Krueger", "Lang", "Lehmann", "Meier", "Mueller",
    "Neumann", "Peters", "Richter", "Schaefer", "Schmidt", "Schneider",
    "Scholz", "Schreiber", "Schulz", "Schwarz", "Wagner", "Walter",
    "Weber", "Weiss", "Werner", "Wolf", "Zimmermann", "Lange", "Becker",
]

# ---------------------------------------------------------------------------
# Abteilungen
# ---------------------------------------------------------------------------
ABTEILUNGEN: list[str] = [
    "Konstruktion",
    "Fertigungsplanung",
    "Qualitaetssicherung",
    "Produktentwicklung",
    "Werkzeugbau",
    "Versuchswesen",
    "Serienentwicklung",
    "Betriebsmittelbau",
    "Einkauf",
    "Lieferantenentwicklung",
    "Prueflabor",
    "Normung",
]

# ---------------------------------------------------------------------------
# Bauteile und Baugruppen
# ---------------------------------------------------------------------------
BAUTEILNAMEN: list[str] = [
    "Gehaeusedeckel", "Antriebswelle", "Lagerhalter", "Dichtungsring",
    "Federhalterung", "Klemmblock", "Schraubenbolzen", "Sicherungsblech",
    "Druckplatte", "Distanzhuelse", "Verbindungsflansch", "Getriebegehaeuse",
    "Spannzylinder", "Kuehlkoerper", "Montagewinkel", "Ritzelwelle",
    "Schaltkulisse", "Bremstraeger", "Oelabscheider", "Luefterrad",
    "Statorgehaeuse", "Kontaktbruecke", "Isolierplatte", "Rastbolzen",
    "Haltelasche", "Schweissbaugruppe", "Zentrierhuelse", "Gleitlager",
    "Schnittstellenmodul", "Kabelkanal", "Traegerplatte", "Spindellager",
]

BAUGRUPPEN: list[str] = [
    "Antriebseinheit / Hauptgetriebe",
    "Fahrwerk / Achsanbindung",
    "Lenkungsanlage / Lenksaeule",
    "Bremsanlage / Bremssattel",
    "Karosserie / Aussenverkleidung",
    "Elektrische Anlage / Steuergeraete",
    "Kuehlsystem / Waermetauscher",
    "Kraftstoffsystem / Einspritzanlage",
    "Hydraulikaggregat / Steuerblock",
    "Pneumatiksystem / Ventilblock",
    "Montageanlage / Zufuehreinheit",
    "Pruefstand / Messsystem",
    "Verpackungsanlage / Foerderband",
    "Roboterarm / Gelenkeinheit",
]

# ---------------------------------------------------------------------------
# Statische Felder
# ---------------------------------------------------------------------------
THEMEN: list[str] = [
    "Konstruktionsfehler",
    "Kundenwunsch",
    "Normaenderung",
    "Fertigungsfehler",
    "Materialaustausch",
    "Sicherheitsanforderung",
]

PRIORITAETEN: list[str] = ["Niedrig", "Mittel", "Hoch", "Kritisch"]

STATUSWERTE: list[str] = ["Entwurf", "In Pruefung", "Freigegeben", "Archiviert"]

DETAIL_LEVELS: list[str] = ["kurz", "mittel", "lang"]
DETAIL_WEIGHTS: list[float] = [0.30, 0.40, 0.30]

DOKUMENTTYPEN: list[str] = [
    "Technische Zeichnung",
    "Montageanweisung",
    "Pruefanweisung",
    "Stueckliste",
    "FMEA-Bericht",
    "Arbeitsplan",
    "Qualitaetsregelplan",
    "Lieferantenspezifikation",
    "Berechnungsnachweis",
    "CE-Akte",
    "Betriebsanleitung",
    "Werkstoffnachweis",
    "Funktionsbeschreibung",
    "Testprotokoll",
    "Audit-Bericht",
]

WERKSTOFFE: list[str] = [
    "S235JR", "S355J2", "1.4301", "1.4571",
    "C45E", "42CrMo4", "EN-GJL-250", "EN-GJS-400-15",
    "EN AW-6060", "EN AW-2024", "PA6-GF30", "POM-C",
    "PTFE", "GFK-EP", "X5CrNi18-10", "16MnCr5",
]

NORMEN: list[str] = [
    "EN ISO 9001:2015", "EN ISO 13849-1", "EN 1090-2",
    "EN ISO 3834-2", "AD 2000-Merkblatt W0", "DIN EN 10025",
    "EN ISO 286-1", "VDI 2230", "EN 15085-2", "ISO 2768-1",
    "DGUV Vorschrift 3", "EN 60204-1", "EN 13480-3",
    "DIN 743", "ISO 1101", "EN ISO 5817",
]

# ---------------------------------------------------------------------------
# Beschreibungs-Templates je Thema
# Platzhalter: {bauteil}, {wert}, {wert2}, {znr}, {rev}, {norm}, {kdnr}, {gnr}, {mat1}, {mat2}
# ---------------------------------------------------------------------------
TOPIC_BESCHREIBUNG: dict[str, list[str]] = {
    "Konstruktionsfehler": [
        "Bei der Ueberpruefung der Bauteilgeometrie wurde eine fehlerhafte Passung zwischen dem {bauteil} und dem angrenzenden Flansch festgestellt.",
        "Die vorliegende Konstruktion des {bauteil} weist eine unzureichende Wandstaerke von {wert} mm im Bereich der Krafteinleitung auf.",
        "Infolge einer nicht ausreichenden Steifigkeit der Haltestruktur kommt es unter Betriebslast zu einer Verformung von bis zu {wert} mm.",
        "Die FEM-Analyse ergab eine kritische Spannungsueberhohung von {wert} MPa im Kerbbereich des {bauteil}.",
        "Der Konstruktionsstand Rev. {rev} enthaelt einen Geometriefehler, der zu einer Kollision mit dem Nachbarbauteil fuehrt.",
        "Durch eine fehlerhafte Toleranzangabe auf Zeichnung {znr} wird eine korrekte Montage des {bauteil} verhindert.",
        "Die bisherige Ausfuehrung des {bauteil} ist fuer die auftretenden Torsionslasten nicht ausreichend dimensioniert.",
        "Ein Zeichnungsfehler in der Stueckliste fuehrt zur Verwechslung von Gleichteilen und verursacht Montageprobleme.",
        "Das Bohrungsmuster in Position 3 des {bauteil} weicht um {wert} mm von der korrekten Referenzebene ab.",
        "Die Schweissnahtvorbereitung entspricht nicht den Vorgaben der Konstruktionsnorm und muss ueberarbeitet werden.",
        "Eine falsche Passung der Lagerbohrung am {bauteil} fuehrt zu erhoehtem Verschleiss nach kurzer Betriebsdauer.",
        "Die Kerbwirkungszahl wurde in der Auslegungsrechnung des {bauteil} zu niedrig angesetzt.",
    ],
    "Kundenwunsch": [
        "Gemaess Kundenanforderung {kdnr} ist die Oberflaechenguete des {bauteil} von Ra {wert} auf Ra {wert2} zu verbessern.",
        "Der Kunde fordert eine Anpassung der Einbaulage des {bauteil}, um einen verbesserten Wartungszugang zu ermoeglichen.",
        "Auf Wunsch des Auftraggebers wird die Farbbeschichtung des {bauteil} von RAL 7035 auf RAL 9005 geaendert.",
        "Der Auftraggeber verlangt eine Erhoehung der Nennlast des {bauteil} von {wert} kN auf {wert2} kN.",
        "Kundenseitig wurde eine Aenderung der Schnittstellengeometrie zur vereinfachten Integration in die Bestandsanlage beauftragt.",
        "Laut Kundenspezifikation {kdnr} ist ein zusaetzlicher Schutzanschluss am {bauteil} vorzusehen.",
        "Die Einbaumasse des {bauteil} sind gemaess aktualisiertem Kundenreferenzmass anzupassen.",
        "Auf Kundenwunsch wird die Werkstoffguete des {bauteil} von {mat1} auf {mat2} erhoeht.",
        "Der Auftraggeber wuenscht die Ergaenzung einer Beschriftung mit Typenbezeichnung und Seriennummer am {bauteil}.",
        "Gemaess Kundenaudit ist eine verbesserte Korrosionsschutzmassnahme fuer das {bauteil} umzusetzen.",
        "Der Auftraggeber hat neue EMV-Anforderungen definiert, die eine Abschirmung am {bauteil} erfordern.",
        "Auf Kundenwunsch ist die Lebensdauer des {bauteil} von {wert} auf {wert2} Betriebsstunden zu erhoehen.",
    ],
    "Normaenderung": [
        "Die ueberarbeitete Norm {norm} tritt zum naechsten Quartal in Kraft und erfordert eine Anpassung der Pruefanforderungen fuer das {bauteil}.",
        "Durch die Neuauflage der {norm} sind geaenderte Mindestanforderungen an die Schweissnahtguete einzuhalten.",
        "Die aktualisierte EN-Norm schreibt eine Kennzeichnungspflicht vor, die am {bauteil} noch nicht umgesetzt ist.",
        "Aufgrund der Normanpassung in {norm} sind neue Pruefintervalle und Nachweispflichten fuer das {bauteil} zu definieren.",
        "Die bisherige Ausfuehrung des {bauteil} entspricht nicht mehr den Anforderungen der ueberarbeiteten {norm}.",
        "Die Revision der {norm} verlangt den Einsatz von Werkstoffen mit verbesserter Kaeltehaerte fuer das {bauteil}.",
        "Mit der Einfuehrung der {norm} entfaellt die bislang verwendete Ausnahmeregelung fuer das {bauteil}.",
        "Die neue Fassung der {norm} schreibt eine CE-Konformitaetserklarung vor, die fuer das {bauteil} zu erstellen ist.",
        "Normspezifische Toleranzfeldaenderungen in {norm} erfordern eine Ueberarbeitung der Zeichnungsangaben.",
        "Der Normausschuss hat eine Aktualisierung der Werkstoffauswahl veroeffentlicht, die das {bauteil} direkt betrifft.",
        "Die harmonisierte Norm {norm} wurde zurueckgezogen; ein Nachfolgedokument ist verbindlich einzufuehren.",
    ],
    "Fertigungsfehler": [
        "Im Rahmen der Wareneingangskontrolle wurden am {bauteil} Massabweichungen von {wert} mm an der Anlaufflaeche festgestellt.",
        "Die Serienfertigung des {bauteil} weist aufgrund von Werkzeugverschleiss systematische Formabweichungen auf.",
        "Bei der Endpruefung wurden {wert} Prozent der gefertigten {bauteil} wegen Oberflaechenfehlern beanstandet.",
        "Ein Einstellfehler an der CNC-Maschine fuehrte zu einer Untermassigkeit der Bohrung am {bauteil} um {wert} mm.",
        "Durch fehlerhafte Waermebehandlungsparameter wurde am {bauteil} eine unzureichende Kernhaerte von {wert} HRC ermittelt.",
        "Der Lieferant hat beim {bauteil} eine abweichende Werkstoffcharge verbaut, die ausserhalb der Spezifikation liegt.",
        "Die Schweissnaht am {bauteil} zeigt Bindefehler, die bei der Ultraschallpruefung aufgedeckt wurden.",
        "Beim {bauteil} liegt eine Positionsabweichung der Gewindebohrungen von {wert} mm vor, was die Montage verhindert.",
        "Aufgrund eines Programmierfehlers im Bearbeitungszentrum weist das {bauteil} eine fehlerhafte Konturgeometrie auf.",
        "Die Beschichtungsdicke am {bauteil} unterschreitet mit {wert} Mikrometer die geforderte Mindestschichtdicke erheblich.",
        "Im Zuge des Serienanlaufs wurden Riefen an der Dichtflaeche des {bauteil} festgestellt, die die Funktion beeintraechtigen.",
    ],
    "Materialaustausch": [
        "Der bisherige Werkstoff {mat1} fuer das {bauteil} ist am Markt nicht mehr lieferbar und wird durch {mat2} ersetzt.",
        "Aufgrund gestiegener Rohstoffkosten wird der Werkstoff des {bauteil} von {mat1} auf das gleichwertige Material {mat2} umgestellt.",
        "Der Alternativwerkstoff {mat2} weist gegenueber {mat1} verbesserte Korrosionseigenschaften auf und ist daher vorzuziehen.",
        "Zur Gewichtsreduzierung des {bauteil} wird der Werkstoff von Stahl {mat1} auf Aluminium {mat2} gewechselt.",
        "Die Lieferkette fuer {mat1} ist aufgrund von Lieferengpaessen unterbrochen; das {bauteil} wird auf {mat2} umgestellt.",
        "Ein qualifizierter Werkstofftest bestaetigt die Gleichwertigkeit von {mat2} als Ersatz fuer {mat1} im {bauteil}.",
        "Zur Verbesserung der Recyclingfaehigkeit wird das {bauteil} zukuenftig aus dem Werkstoff {mat2} gefertigt.",
        "Der Wechsel von {mat1} auf {mat2} beim {bauteil} erfordert eine Anpassung der Schweissparameter.",
        "Durch den Einsatz von {mat2} anstelle von {mat1} kann die Bearbeitungszeit des {bauteil} um {wert} Prozent gesenkt werden.",
        "Die Festigkeitskennwerte von {mat2} ermoglichen beim {bauteil} eine Wandstaerkenreduzierung von {wert} mm.",
        "Ein Lieferantenaudit hat ergeben, dass {mat1} kuenftig nicht mehr in zertifizierter Guete beschaffbar ist.",
    ],
    "Sicherheitsanforderung": [
        "Gemaess Gefaehrdungsbeurteilung ist am {bauteil} eine zusaetzliche Sicherung gegen unbeabsichtigtes Loesen vorzusehen.",
        "Die Risikoanalyse nach EN ISO 13849 ergab fuer das {bauteil} einen unzulaessigen Performance Level; die Konstruktion ist anzupassen.",
        "Aufgrund eines sicherheitsrelevanten Vorkommnisses im Feld ist das {bauteil} mit einem Ueberlastschutz nachzuruestaen.",
        "Die aktuelle Ausfuehrung des {bauteil} erfuellt nicht die Anforderungen der Maschinenrichtlinie 2006/42/EG.",
        "Zur Vermeidung von Quetschgefahren ist am {bauteil} ein Schutzgitter mit lichtem Abstand von maximal {wert} mm vorzusehen.",
        "Das {bauteil} ist mit einem Warnhinweis gemaess ISO 11684 zu kennzeichnen.",
        "Auf Basis des FMEA-Berichts ist eine Redundanz im Notabschaltsystem durch ein zweites {bauteil} herzustellen.",
        "Das Bauteil unterschreitet im derzeitigen Zustand den geforderten Sicherheitsabstand gemaess DGUV Vorschrift.",
        "Sicherheitstechnische Nachweise verlangen eine Neuberechnung des {bauteil} fuer den Ueberdruck-Fall.",
        "Im Rahmen der CE-Kennzeichnungspflicht ist fuer das {bauteil} eine dokumentierte Restlebensdauerabschaetzung zu erstellen.",
        "Eine externe Pruefstelle hat bei der Typenpruefung eine sicherheitsrelevante Abweichung am {bauteil} festgestellt.",
    ],
}

# ---------------------------------------------------------------------------
# Begruendungs-Templates je Thema
# ---------------------------------------------------------------------------
TOPIC_BEGRUENDUNG: dict[str, list[str]] = {
    "Konstruktionsfehler": [
        "Die Fehlerursache wurde im Zuge einer internen Konstruktionsreview identifiziert und auf eine fehlerhafte CAD-Datenuebertragung zurueckgefuehrt.",
        "Ursaechlich ist eine unvollstaendige Lastfallbetrachtung in der initialen Auslegungsphase; Betriebslasten wurden zu niedrig angesetzt.",
        "Die Zeichnung wurde ohne Freigabe durch den zustaendigen Konstruktionsverantwortlichen in Umlauf gebracht.",
        "Durch die Konstruktionsaenderung wird das Auftreten von Schwingungsrissen im Betrieb nachhaltig verhindert.",
        "Die Nichtkonformitaet wurde im Rahmen eines internen Audits festgestellt; eine Anpassung ist zur Seriensicherheit erforderlich.",
        "Ein fehlerhafter Abgleich zwischen CAD-Modell und Fertigungszeichnung fuehrte zur Abweichung.",
    ],
    "Kundenwunsch": [
        "Der Auftraggeber hat die Anforderungsaenderung im Rahmen des Design Reviews schriftlich beauftragt.",
        "Die Aenderung ergibt sich aus dem aktualisierten Pflichtenheft {kdnr} und ist fuer die Freigabe der Baumusterpruefung erforderlich.",
        "Kundenseitig wurde die Notwendigkeit anhand von Felderfahrungen aus dem Vorprojekt belegt.",
        "Die Umsetzung ist Voraussetzung fuer die Serienfreigabe durch den Auftraggeber.",
        "Ohne diese Aenderung ist eine Integration in die Fahrzeugplattform des Kunden technisch nicht moeglich.",
        "Der Auftraggeber hat die Anforderung im letzten Kundengespraech ausdruecklich als vertragsrelevant eingestuft.",
    ],
    "Normaenderung": [
        "Die Ubergangsfrist der alten Normfassung ist abgelaufen; ab sofort ist ausschliesslich die neue Revision anzuwenden.",
        "Der Normgeber hat die Aenderung aufgrund neuer Erkenntnisse zur Materialermuedung eingefuehrt.",
        "Eine Nichtkonformitaet mit {norm} wuerde zum Erloeschen der CE-Kennzeichnung fuehren.",
        "Die Normaenderung ist das Ergebnis eines europaeischen Abstimmungsprozesses und bindet alle Mitglieder.",
        "Das interne Normwesen hat die Relevanz der Normanpassung fuer das Produktportfolio bestaetigt.",
        "Der Normtext wurde in einem Erratumblatt praezisiert, das unmittelbare Auswirkungen auf das {bauteil} hat.",
    ],
    "Fertigungsfehler": [
        "Die Ursachenanalyse nach 8D-Methode ergab einen systematischen Einstellfehler an der betroffenen Maschine.",
        "Eine Abweichung im Fertigungsprozess wurde durch die statistische Prozesskontrolle (SPC) fruehzeitig detektiert.",
        "Der Fehler ist auf eine fehlende Pruefanweisung zurueckzufuehren; das Pruefmittel war nicht kalibriert.",
        "Bereits gefertigte Teile werden einer 100-Prozent-Nachpruefung unterzogen; nicht konforme Teile werden gesperrt.",
        "Zur dauerhaften Fehlerbeseitigung werden die Fertigungsparameter aktualisiert und im Arbeitsplanungssystem hinterlegt.",
        "Eine Lieferantenbegehung hat ergeben, dass die Einhaltung der Fertigungsvorschriften nicht konsequent ueberwacht wurde.",
    ],
    "Materialaustausch": [
        "Der Lieferant hat die Einstellung der Produktion des Werkstoffs {mat1} angekuendigt.",
        "Werkstoffpruefungen (Zugversuch, Kerbschlagbiegeversuch) belegen die Gleichwertigkeit des Ersatzwerkstoffs {mat2}.",
        "Die Beschaffungsabteilung hat drei Alternativlieferanten evaluiert; {mat2} erfuellt alle Anforderungen.",
        "Der Werkstoffwechsel wird durch eine angepasste Fertigungsfreigabe und aktualisierte Pruefplaene begleitet.",
        "Alle bestehenden Berechnungsnachweise werden auf Basis der Kennwerte des neuen Werkstoffs {mat2} aktualisiert.",
        "Ein Kostenvergleich zeigt, dass {mat2} bei gleichwertigen Eigenschaften deutlich guenstiger beschaffbar ist.",
    ],
    "Sicherheitsanforderung": [
        "Die Sicherheitsluecke wurde im Rahmen einer Beinahe-Unfall-Analyse identifiziert.",
        "Die Bewertung durch den Sicherheitsbeauftragten ergab eine inakzeptable Risikoprioritaetszahl im FMEA-Register.",
        "Ohne Umsetzung der Massnahme kann die CE-Konformitaetserklarung nicht aufrechterhalten werden.",
        "Eine externe Pruefstelle hat im Rahmen des Typspruefverfahrens auf die sicherheitsrelevante Abweichung hingewiesen.",
        "Die Massnahmen wurden mit dem Betriebsrat und der Fachkraft fuer Arbeitssicherheit abgestimmt.",
        "Ein Rueckruf vergleichbarer Serienteile beim Wettbewerb hat die Dringlichkeit der Massnahme unterstrichen.",
    ],
}

# ---------------------------------------------------------------------------
# Massnahmen-Templates je Thema
# ---------------------------------------------------------------------------
TOPIC_MASSNAHMEN: dict[str, list[str]] = {
    "Konstruktionsfehler": [
        "Ueberarbeitung der Konstruktionszeichnung {znr} in Rev. {rev_new} mit korrigierter Bemassung",
        "FEM-Neuberechnung des {bauteil} unter Beruecksichtigung der tatsaechlichen Betriebslasten",
        "Anpassung der Wandstaerke von {wert} mm auf {wert2} mm im Bereich der Krafteinleitung",
        "Aktualisierung der Stueckliste und Freigabe durch den Konstruktionsverantwortlichen",
        "Durchfuehrung einer Erstmusterpruefung (EMPB) nach der Konstruktionsaenderung",
        "Ueberpruefung aller Gleichteile auf uebertragbare Fehler im gleichen Bauteilsortiment",
        "Validierung der geaenderten Konstruktion mittels Betriebslastversuch",
    ],
    "Kundenwunsch": [
        "Anpassung der Zeichnungsunterlagen entsprechend der aktualisierten Kundenspezifikation {kdnr}",
        "Abstimmung der geaenderten Schnittstellenmasse mit dem Kunden und Gegenzeichnung",
        "Erstellung eines Aenderungsnachweises im Kundenportal",
        "Durchfuehrung einer Kundenmusterpruefung vor Serienanlauf",
        "Aktualisierung des Qualitaetsregelplans und der Pruefanweisung",
        "Information der Fertigungsplanung ueber geaenderte Bearbeitungsparameter",
        "Terminabstimmung mit dem Auftraggeber fuer die Freigabe der Erstlieferung",
    ],
    "Normaenderung": [
        "Ueberarbeitung der technischen Dokumentation gemaess {norm}",
        "Durchfuehrung einer erneuten Konformitaetsbewertung und Aktualisierung der CE-Akte",
        "Anpassung der internen Pruefanweisung an die neuen Normvorgaben",
        "Schulung der betroffenen Mitarbeiter in Fertigung und Qualitaetssicherung",
        "Aktualisierung der Zeichnungsangaben fuer Schweissnahtguete und Toleranzklassen",
        "Einholung eines aktualisierten Werkstoffnachweises gemaess neuer Norm",
        "Uebermittlung der ueberarbeiteten Unterlagen an die benannte Stelle",
    ],
    "Fertigungsfehler": [
        "Sperrung und Nachpruefung aller Teile aus dem betroffenen Fertigungslos",
        "Korrekturmassnahme an der Fertigungsmaschine und erneute Einstellabnahme",
        "Aktualisierung der Pruefanweisung und Einfuehrung eines Zwischenpruefschritts",
        "Rueckmeldung an den Lieferanten mit 8D-Bericht und Forderung nach Gegenmassnahmen",
        "Nachkalibrierung aller betroffenen Messmittel nach DIN EN ISO 10012",
        "Anpassung der SPC-Regelkarte und Absenkung der Eingriffsgrenzen",
        "Freigabe der korrigierten Teile nach bestandener Erstmusterpruefung",
    ],
    "Materialaustausch": [
        "Qualifizierung des Ersatzwerkstoffs {mat2} durch Lieferanten- und Werkstoffaudit",
        "Aktualisierung der Zeichnung mit neuem Werkstoffeintrag und Normbezeichnung",
        "Anpassung der Schweissparameter und Waermebehandlungsvorschriften auf {mat2}",
        "Erstellung eines Werkstofffreigabeblatts und Ablage im Qualitaetsmanagementsystem",
        "Benachrichtigung des Einkaufs zur Anpassung der Bestellspezifikation",
        "Erstmusterpruefung mit dem neuen Werkstoff inkl. Werkstoffzeugnis 3.1 nach EN 10204",
        "Ueberarbeitung der Berechnungsnachweise mit den Kennwerten von {mat2}",
    ],
    "Sicherheitsanforderung": [
        "Konstruktive Nachriestung des {bauteil} mit Ueberlastsicherung gemaess Risikobeurteilung",
        "Anbringung von Sicherheitskennzeichnung und Warnhinweisen nach ISO 11684",
        "Aktualisierung der Betriebsanleitung mit erweiterten Sicherheitshinweisen",
        "Dokumentation der Schutzmassnahmen in der CE-Akte",
        "Durchfuehrung einer abschliessenden Funktionspruefung durch den Sicherheitsbeauftragten",
        "Meldung der Aenderung an die benannte Stelle und Aktualisierung der Baumusterpruefung",
        "Schulung der Bediener und Wartungsverantwortlichen an der geaenderten Sicherheitseinrichtung",
    ],
}
