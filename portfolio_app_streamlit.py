import json
import os
import csv
import io
from dataclasses import dataclass, asdict, field
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_data.json")


FONDS = {
    "verbrauchstopf": {
        "name": "Verbrauchstopf",
        "kurz": "Geld fuer das naechste Jahr",
        "produkt": "Tagesgeld oder Geldmarkt-ETF",
        "erklaerung": "Hier liegt das Geld, das in den naechsten 12 Monaten gebraucht wird. Es soll moeglichst wenig schwanken.",
    },
    "zinstopf": {
        "name": "Zinstopf",
        "kurz": "Sicherheit fuer die darauffolgenden 3 Jahre",
        "produkt": "Fixed Income One R (Ausschuettend)",
        "erklaerung": "Hier liegt Geld fuer die Jahre 2 bis 4. Es darf etwas mehr Rendite bringen, soll aber deutlich ruhiger sein als Aktien.",
    },
    "investitionstopf": {
        "name": "Investitionstopf",
        "kurz": "Langfristiges Wachstum",
        "produkt": "Xtrackers Portfolio ETF",
        "erklaerung": "Hier liegt alles Geld, das langfristig arbeiten soll. Dieser Topf darf schwanken, weil er fuer spaeter gedacht ist.",
    },
}


@dataclass
class Portfolio:
    verbrauchstopf: float = 0.0
    zinstopf: float = 0.0
    investitionstopf: float = 0.0
    jahresverbrauch: float = 0.0
    setup_abgeschlossen: bool = False
    history: list = field(default_factory=list)

    @property
    def ziel_verbrauch(self):
        return self.jahresverbrauch

    @property
    def ziel_zins(self):
        return self.jahresverbrauch * 3

    @property
    def gesamt(self):
        return self.verbrauchstopf + self.zinstopf + self.investitionstopf

    @property
    def ziel_investitionstopf(self):
        return max(0.0, self.gesamt - self.ziel_verbrauch - self.ziel_zins)

    def log(self, aktion, details):
        self.history.append({
            "datum": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "aktion": aktion,
            "details": details,
            "verbrauchstopf": round(self.verbrauchstopf, 2),
            "zinstopf": round(self.zinstopf, 2),
            "investitionstopf": round(self.investitionstopf, 2),
        })


def load_portfolio() -> Portfolio:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Portfolio(**data)
        except Exception:
            pass
    return Portfolio()


def save_portfolio(p: Portfolio):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(p), f, ensure_ascii=False, indent=2)


def euro(x):
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def kapitalzufuhr_plan(p: Portfolio, neues_kapital: float):
    rest = neues_kapital
    plan = {}

    bedarf_verbrauch = max(0.0, p.ziel_verbrauch - p.verbrauchstopf)
    zuweisung_verbrauch = min(rest, bedarf_verbrauch)
    plan["verbrauchstopf"] = zuweisung_verbrauch
    rest -= zuweisung_verbrauch

    bedarf_zins = max(0.0, p.ziel_zins - p.zinstopf)
    zuweisung_zins = min(rest, bedarf_zins)
    plan["zinstopf"] = zuweisung_zins
    rest -= zuweisung_zins

    plan["investitionstopf"] = rest
    return plan


def kapitalzufuhr_anwenden(p: Portfolio, plan: dict, neues_kapital: float):
    p.verbrauchstopf += plan["verbrauchstopf"]
    p.zinstopf += plan["zinstopf"]
    p.investitionstopf += plan["investitionstopf"]
    p.log(
        "Kapitalzufuhr",
        f"{neues_kapital:.2f} Euro eingezahlt -> Verbrauch: {plan['verbrauchstopf']:.2f}, Zins: {plan['zinstopf']:.2f}, Investition: {plan['investitionstopf']:.2f}",
    )


def rebalancing_plan(p: Portfolio):
    ziel = {
        "verbrauchstopf": p.ziel_verbrauch,
        "zinstopf": p.ziel_zins,
        "investitionstopf": p.ziel_investitionstopf,
    }
    ist = {
        "verbrauchstopf": p.verbrauchstopf,
        "zinstopf": p.zinstopf,
        "investitionstopf": p.investitionstopf,
    }
    diff = {k: ist[k] - ziel[k] for k in ziel}

    ueberschuss = {k: v for k, v in diff.items() if v > 0.01}
    fehlbetrag = {k: -v for k, v in diff.items() if v < -0.01}

    transfers = []
    ueberschuss = dict(ueberschuss)
    fehlbetrag = dict(fehlbetrag)

    for von_topf in list(ueberschuss.keys()):
        while ueberschuss.get(von_topf, 0) > 0.01 and fehlbetrag:
            nach_topf = next(iter(fehlbetrag))
            betrag = min(ueberschuss[von_topf], fehlbetrag[nach_topf])
            transfers.append((von_topf, nach_topf, betrag))
            ueberschuss[von_topf] -= betrag
            fehlbetrag[nach_topf] -= betrag
            if fehlbetrag[nach_topf] <= 0.01:
                del fehlbetrag[nach_topf]

    return ziel, ist, diff, transfers


def rebalancing_anwenden(p: Portfolio, transfers: list):
    for von_topf, nach_topf, betrag in transfers:
        setattr(p, von_topf, getattr(p, von_topf) - betrag)
        setattr(p, nach_topf, getattr(p, nach_topf) + betrag)
    details = "; ".join([f"{FONDS[v]['name']} -> {FONDS[n]['name']}: {b:.2f} Euro" for v, n, b in transfers])
    p.log("Rebalancing", details if details else "Keine Anpassung notwendig")


def entnahme_plan(p: Portfolio, krise: bool):
    entnahme = min(p.verbrauchstopf, p.jahresverbrauch)
    verbrauchstopf_neu = p.verbrauchstopf - entnahme
    fehlbetrag_verbrauch = p.ziel_verbrauch - verbrauchstopf_neu
    fehlbetrag_zins = max(0.0, p.ziel_zins - p.zinstopf)

    aus_zins = 0.0
    aus_invest = 0.0
    an_verbrauch = 0.0
    an_zins = 0.0

    if krise:
        aus_zins = min(max(0.0, fehlbetrag_verbrauch), p.zinstopf)
        an_verbrauch = aus_zins
    else:
        gesamtbedarf = max(0.0, fehlbetrag_verbrauch) + fehlbetrag_zins
        aus_invest = min(gesamtbedarf, p.investitionstopf)
        an_verbrauch = min(aus_invest, max(0.0, fehlbetrag_verbrauch))
        an_zins = aus_invest - an_verbrauch

    return {
        "entnahme": entnahme,
        "aus_zins": aus_zins,
        "aus_invest": aus_invest,
        "an_verbrauch": an_verbrauch,
        "an_zins": an_zins,
        "krise": krise,
    }


def entnahme_anwenden(p: Portfolio, plan: dict):
    p.verbrauchstopf -= plan["entnahme"]
    p.zinstopf -= plan["aus_zins"]
    p.investitionstopf -= plan["aus_invest"]
    p.verbrauchstopf += plan["an_verbrauch"]
    p.zinstopf += plan["an_zins"]
    modus = "Krise (Auffuellen aus Zinstopf)" if plan["krise"] else "Normalfall (Auffuellen aus Investitionstopf)"
    p.log(
        "Jaehrliche Entnahme",
        f"Entnommen: {plan['entnahme']:.2f} Euro | Modus: {modus} | Aus Zinstopf: {plan['aus_zins']:.2f} | Aus Investitionstopf: {plan['aus_invest']:.2f}",
    )


def info_box(title, text):
    st.markdown(f"### {title}")
    st.info(text)


st.set_page_config(page_title="Einfache Drei-Toepfe-App", page_icon="💶", layout="wide")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

p = st.session_state.portfolio

st.title("💶 Einfache Drei-Toepfe-App")
st.caption("Diese App hilft dabei, Geld einfach auf drei Toepfe zu verteilen und zu pflegen.")

with st.expander("Erst lesen: Worum geht es hier?", expanded=not p.setup_abgeschlossen):
    st.markdown(
        "Diese App teilt dein Geld in **drei einfache Toepfe** ein. "
        "Die Idee ist nur: Geld, das du bald brauchst, "
        "soll sicher liegen. Geld fuer spaeter darf mehr Rendite bringen und auch schwanken."
    )
    st.markdown(
        "- **Verbrauchstopf:** Geld fuer das naechste Jahr.\n"
        "- **Zinstopf:** Reserve fuer die darauffolgenden 3 Jahre.\n"
        "- **Investitionstopf:** Geld fuer langfristiges Wachstum."
    )
    st.markdown(
        "Die Aufteilung orientiert sich an deinem jaehrlichen Geldbedarf. "
        "Die Regel ist: 1 Jahr im Verbrauchstopf, 3 Jahre im Zinstopf und der Rest im Investitionstopf."
    )

with st.sidebar:
    st.header("Schritte")
    schritt = st.radio(
        "Bitte der Reihe nach vorgehen:",
        [
            "1. Verstehen",
            "2. Einrichten",
            "3. Neues Geld verteilen",
            "4. Rebalancing / Anpassen",
            "5. Jaehrliche Entnahme",
            "6. Verlauf",
        ],
    )
    st.divider()
    st.metric("Gesamt", euro(p.gesamt))


if schritt == "1. Verstehen":
    st.subheader("Die drei Toepfe einfach erklaert")
    cols = st.columns(3)
    for col, key in zip(cols, ["verbrauchstopf", "zinstopf", "investitionstopf"]):
        with col:
            st.markdown(f"#### {FONDS[key]['name']}")
            st.success(FONDS[key]["kurz"])
            st.write(FONDS[key]["erklaerung"])
            st.caption(FONDS[key]["produkt"])

    st.markdown("### Wie gross sollen die Toepfe sein?")
    st.write(
        "Laut Regel soll der Verbrauchstopf **1 Jahresbedarf**, der Zinstopf **3 Jahresbedarfe** und der Investitionstopf **der ganze Rest** sein."
    )
    beispiel = st.number_input("Beispiel: Jahresbedarf eingeben", min_value=0.0, value=24000.0, step=1000.0)
    st.write(f"- Verbrauchstopf: {euro(beispiel)}")
    st.write(f"- Zinstopf: {euro(beispiel * 3)}")
    st.write(f"- Zusammen fuer die ersten 4 Jahre: {euro(beispiel * 4)}")
    st.info("Merksatz: 1 Jahr sofort verfuegbar, 3 Jahre Reserve, Rest fuer spaeter.")


elif schritt == "2. Einrichten":
    st.subheader("Schritt 1: Einmal alles eintragen")
    info_box(
        "Was mache ich hier?",
        "Hier traegst du zuerst ein, wie viel Geld du pro Jahr brauchst und wie viel aktuell in deinen drei Fonds liegt. Danach weiss die App, wie die Zielverteilung aussehen soll.",
    )

    jahresverbrauch = st.number_input(
        "Wie viel Geld brauchst du pro Jahr aus dem Portfolio?", min_value=0.0, value=float(p.jahresverbrauch), step=1000.0
    )
    st.markdown("**Daraus berechnet die App automatisch:**")
    st.write(f"- Ziel Verbrauchstopf: {euro(jahresverbrauch)}")
    st.write(f"- Ziel Zinstopf: {euro(jahresverbrauch * 3)}")
    st.write("- Ziel Investitionstopf: alles, was danach noch uebrig ist")

    st.markdown("### Jetzt die aktuellen Werte aus dem Depot eingeben")
    c1, c2, c3 = st.columns(3)
    with c1:
        v = st.number_input("Aktueller Verbrauchstopf", min_value=0.0, value=float(p.verbrauchstopf), step=500.0)
    with c2:
        z = st.number_input("Aktueller Zinstopf", min_value=0.0, value=float(p.zinstopf), step=500.0)
    with c3:
        i = st.number_input("Aktueller Investitionstopf", min_value=0.0, value=float(p.investitionstopf), step=500.0)

    if st.button("Speichern", type="primary"):
        p.jahresverbrauch = jahresverbrauch
        p.verbrauchstopf = v
        p.zinstopf = z
        p.investitionstopf = i
        p.setup_abgeschlossen = True
        p.log("Einrichtung", f"Jahresverbrauch={jahresverbrauch:.2f}, Verbrauch={v:.2f}, Zins={z:.2f}, Invest={i:.2f}")
        save_portfolio(p)
        st.success("Gespeichert. Jetzt kannst du mit neuem Geld oder Rebalancing weitermachen.")
        st.rerun()


elif schritt == "3. Neues Geld verteilen":
    st.subheader("Schritt 2: Neues Geld verteilen")
    info_box(
        "Was passiert hier?",
        "Wenn neues Geld dazukommt, verteilt die App es automatisch sinnvoll: zuerst in den Verbrauchstopf, dann in den Zinstopf und erst am Schluss in den Investitionstopf.",
    )

    if not p.setup_abgeschlossen:
        st.error("Bitte zuerst Schritt 2 'Einrichten' ausfuellen.")
    else:
        betrag = st.number_input("Wie viel neues Geld willst du anlegen?", min_value=0.0, value=0.0, step=500.0)
        if betrag > 0:
            plan = kapitalzufuhr_plan(p, betrag)
            st.markdown("### So solltest du das Geld verteilen")
            st.write(f"- In den Verbrauchstopf: **{euro(plan['verbrauchstopf'])}**")
            st.write(f"- In den Zinstopf: **{euro(plan['zinstopf'])}**")
            st.write(f"- In den Investitionstopf: **{euro(plan['investitionstopf'])}**")

            st.markdown("### Was musst du im echten Depot tun?")
            for key in ["verbrauchstopf", "zinstopf", "investitionstopf"]:
                if plan[key] > 0.01:
                    st.write(f"- Kaufe {euro(plan[key])} von {FONDS[key]['produkt']}")

            if st.button("Verbuchung bestaetigen", type="primary"):
                kapitalzufuhr_anwenden(p, plan, betrag)
                save_portfolio(p)
                st.success("Verbucht. Bitte dieselben Kaeufe jetzt auch im echten Depot ausfuehren.")
                st.rerun()


elif schritt == "4. Rebalancing / Anpassen":
    st.subheader("Schritt 3: Pruefen und wieder richtig verteilen")
    info_box(
        "Was bedeutet Rebalancing?",
        "Manchmal wachsen die Toepfe unterschiedlich stark. Dann passt die urspruengliche Verteilung nicht mehr. Rebalancing bedeutet: wieder in die Zielverteilung zurueckkehren.",
    )
    st.write("Du trägst unten einfach die **aktuellen Depotwerte** ein. Dann zeigt die App, was verkauft und was gekauft werden sollte.")

    c1, c2, c3 = st.columns(3)
    with c1:
        v_ist = st.number_input("Aktueller Verbrauchstopf", min_value=0.0, value=float(p.verbrauchstopf), step=500.0, key="rv")
    with c2:
        z_ist = st.number_input("Aktueller Zinstopf", min_value=0.0, value=float(p.zinstopf), step=500.0, key="rz")
    with c3:
        i_ist = st.number_input("Aktueller Investitionstopf", min_value=0.0, value=float(p.investitionstopf), step=500.0, key="ri")

    if st.button("Rebalancing berechnen", type="primary"):
        p.verbrauchstopf, p.zinstopf, p.investitionstopf = v_ist, z_ist, i_ist
        save_portfolio(p)
        st.rerun()

    ziel, ist, diff, transfers = rebalancing_plan(p)
    df = pd.DataFrame({
        "Topf": [FONDS[k]["name"] for k in ziel],
        "Ist": [ist[k] for k in ziel],
        "Soll": [ziel[k] for k in ziel],
        "Abweichung": [diff[k] for k in ziel],
    })
    st.dataframe(df.style.format({"Ist": euro, "Soll": euro, "Abweichung": lambda x: ("+" if x >= 0 else "") + euro(x)}), use_container_width=True)

    st.markdown("### Konkrete Anleitung")
    if not transfers:
        st.success("Alles passt bereits. Du musst nichts umschichten.")
    else:
        for von, nach, betrag in transfers:
            st.write(f"- Verkaufe {euro(betrag)} aus **{FONDS[von]['name']}** und kaufe dafuer **{FONDS[nach]['name']}**.")
        if st.button("Rebalancing verbuchen"):
            rebalancing_anwenden(p, transfers)
            save_portfolio(p)
            st.success("Verbucht. Bitte dieselben Umschichtungen nun auch im echten Depot ausfuehren.")
            st.rerun()


elif schritt == "5. Jaehrliche Entnahme":
    st.subheader("Schritt 4: Geld fuer das Jahr entnehmen")
    info_box(
        "Was passiert hier?",
        "Einmal pro Jahr wird Geld aus dem Verbrauchstopf entnommen. Danach wird der Topf wieder aufgefuellt. Im Normalfall kommt das Geld aus dem Investitionstopf. In einer Boersenkrise kommt es aus dem Zinstopf.",
    )
    krise = st.checkbox("Sind die Aktienmaerkte gerade in einer Krise?")
    plan = entnahme_plan(p, krise)

    st.markdown("### So geht es jetzt weiter")

    if p.verbrauchstopf >= p.jahresverbrauch:
        st.success("Der Verbrauchstopf reicht fuer die geplante Jahresentnahme aus.")
    else:
        st.warning("Der Verbrauchstopf reicht nicht vollstaendig aus. Die App zeigt dir unten, wie aufgefuellt werden soll.")

    st.write(f"- Geplanter Jahresbedarf: **{euro(p.jahresverbrauch)}**")
    st.write(f"- Aktuell im Verbrauchstopf: **{euro(p.verbrauchstopf)}**")
    st.write(f"- Tatsaechlich jetzt entnehmen: **{euro(plan['entnahme'])}**")

    restbedarf = max(0.0, p.jahresverbrauch - plan["entnahme"])
    if restbedarf > 0.01:
        st.write(f"- Danach fehlen noch: **{euro(restbedarf)}**")

    if plan["aus_zins"] > 0.01:
        st.write(f"- Nimm **{euro(plan['aus_zins'])}** aus dem Zinstopf und lege es in den Verbrauchstopf.")

    if plan["aus_invest"] > 0.01:
        st.write(f"- Verkaufe insgesamt **{euro(plan['aus_invest'])}** aus dem Investitionstopf.")
        if plan["an_verbrauch"] > 0.01:
            st.write(f"- Lege davon **{euro(plan['an_verbrauch'])}** in den Verbrauchstopf.")
        if plan["an_zins"] > 0.01:
            st.write(f"- Lege davon **{euro(plan['an_zins'])}** in den Zinstopf.")

    if plan["aus_zins"] <= 0.01 and plan["aus_invest"] <= 0.01:
        st.info("Es ist keine weitere Umschichtung noetig.")

    if st.button("Entnahme verbuchen", type="primary"):
        entnahme_anwenden(p, plan)
        save_portfolio(p)
        st.success("Verbucht. Bitte dieselben Verkaeufe/Kauefe jetzt im echten Depot ausfuehren.")
        st.rerun()


elif schritt == "6. Verlauf":
    st.subheader("Bisherige Aktionen")
    if p.history:
        df_hist = pd.DataFrame(p.history[::-1])
        st.dataframe(df_hist, use_container_width=True, height=400)
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=p.history[0].keys())
        writer.writeheader()
        writer.writerows(p.history)
        st.download_button("Verlauf als CSV herunterladen", data=csv_buf.getvalue(), file_name="portfolio_verlauf.csv", mime="text/csv")
    else:
        st.info("Noch kein Verlauf vorhanden.")


st.divider()
st.caption("Hinweis: Diese App fuehrt keine echten Banktransaktionen aus. Sie zeigt nur, was du in deinem echten Depot tun solltest. Die Logik ist: 1 Jahr Verbrauchstopf, 3 Jahre Zinstopf und der Rest im Investitionstopf.")
