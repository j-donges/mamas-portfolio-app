"""
Drei-Toepfe-Portfolio
----------------------
Eine klar strukturierte Streamlit-App zur Verwaltung eines Vermoegens nach dem
Drei-Toepfe-Prinzip: 1 Jahr im Verbrauchstopf, 3 Jahre im Zinstopf, der Rest
im Investitionstopf.

Start (im Terminal / in der PowerShell):
    cd C:\\Users\\jdonges\\Downloads
    streamlit run Portfolio_Mama.py

Die App fuehrt keine echten Banktransaktionen aus. Sie zeigt nur, was im
echten Depot getan werden sollte.
"""

import json
import os
import csv
import io
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Konstanten und Design-Palette
# ---------------------------------------------------------------------------

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio_data.json")
BACKUP_FILE = DATA_FILE + ".backup"

# Zurueckhaltende, seriöse Farbpalette (Navy / Teal / Slate).
COLORS = {
    "primary": "#1B2A4A",     # dunkles Navy  – Kopf/Text
    "accent": "#2F6F6A",      # gedecktes Teal – Aktionen
    "bg": "#F5F7FA",          # heller Hintergrund
    "card": "#FFFFFF",        # Kartenflaeche
    "line": "#E3E8EF",        # Trennlinien
    "muted": "#6B7280",       # Sekundaertext
    "good": "#2F7D5B",        # positiv
    "warn": "#B45309",        # Hinweis
}

# Jeder Topf bekommt eine eigene, dezente Farbe – konsistent in App und Diagramm.
FONDS = {
    "verbrauchstopf": {
        "name": "Verbrauchstopf",
        "farbe": "#2F6F6A",
        "kurz": "Geld fuer das naechste Jahr",
        "produkt": "Tagesgeld oder Geldmarkt-ETF",
        "erklaerung": "Hier liegt das Geld, das in den naechsten 12 Monaten "
                      "gebraucht wird. Es soll moeglichst wenig schwanken.",
    },
    "zinstopf": {
        "name": "Zinstopf",
        "farbe": "#C79A3A",
        "kurz": "Sicherheit fuer die darauffolgenden 3 Jahre",
        "produkt": "Fixed Income One R (Ausschuettend)",
        "erklaerung": "Hier liegt Geld fuer die Jahre 2 bis 4. Es darf etwas "
                      "mehr Rendite bringen, soll aber deutlich ruhiger sein als Aktien.",
    },
    "investitionstopf": {
        "name": "Investitionstopf",
        "farbe": "#3E5C89",
        "kurz": "Langfristiges Wachstum",
        "produkt": "Xtrackers Portfolio ETF",
        "erklaerung": "Hier liegt alles Geld, das langfristig arbeiten soll. "
                      "Dieser Topf darf schwanken, weil er fuer spaeter gedacht ist.",
    },
}

TOPF_KEYS = ["verbrauchstopf", "zinstopf", "investitionstopf"]


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
            "Datum": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "Aktion": aktion,
            "Details": details,
            "Verbrauchstopf": round(self.verbrauchstopf, 2),
            "Zinstopf": round(self.zinstopf, 2),
            "Investitionstopf": round(self.investitionstopf, 2),
        })


# ---------------------------------------------------------------------------
# Speichern / Laden (mit Sicherheitskopie)
# ---------------------------------------------------------------------------

def load_portfolio() -> Portfolio:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Alte Verlaufsformate tolerieren
            return Portfolio(**data)
        except Exception:
            pass
    return Portfolio()


def save_portfolio(p: Portfolio):
    if os.path.exists(DATA_FILE):
        try:
            shutil.copyfile(DATA_FILE, BACKUP_FILE)
        except Exception:
            pass
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(p), f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def euro(x):
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def card(inner_html: str):
    """Rendert einen Inhalt in einer dezenten Karte."""
    st.markdown(f"<div class='card'>{inner_html}</div>", unsafe_allow_html=True)


def section_title(text: str, sub: str = ""):
    sub_html = f"<div class='section-sub'>{sub}</div>" if sub else ""
    st.markdown(
        f"<div class='section-title'>{text}</div>{sub_html}",
        unsafe_allow_html=True,
    )


def hinweis(text: str, art: str = "info"):
    farbe = {"info": COLORS["accent"], "warn": COLORS["warn"], "good": COLORS["good"]}[art]
    st.markdown(
        f"<div class='hinweis' style='border-left-color:{farbe};'>{text}</div>",
        unsafe_allow_html=True,
    )


def donut_chart(p: Portfolio):
    werte = [getattr(p, k) for k in TOPF_KEYS]
    if sum(werte) <= 0:
        return None
    fig = go.Figure(data=[go.Pie(
        labels=[FONDS[k]["name"] for k in TOPF_KEYS],
        values=werte,
        hole=0.68,
        marker=dict(colors=[FONDS[k]["farbe"] for k in TOPF_KEYS],
                    line=dict(color="#FFFFFF", width=2)),
        textinfo="percent",
        textfont=dict(size=15, color="#FFFFFF", family="Segoe UI"),
        sort=False,
        hovertemplate="%{label}: %{value:,.0f} €<extra></extra>",
    )])
    fig.add_annotation(
        text=f"<b>{euro(p.gesamt)}</b><br><span style='font-size:12px;color:{COLORS['muted']}'>Gesamt</span>",
        showarrow=False, font=dict(size=17, color=COLORS["primary"], family="Segoe UI"),
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5,
                    font=dict(size=13, color=COLORS["primary"])),
        height=300,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def bucket_metric(col, key, value):
    f = FONDS[key]
    col.markdown(
        f"""
        <div class='metric-card'>
            <div class='metric-bar' style='background:{f['farbe']};'></div>
            <div class='metric-label'>{f['name']}</div>
            <div class='metric-value'>{euro(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_uebersicht(p: Portfolio):
    left, right = st.columns([1.4, 1])
    with left:
        cols = st.columns(3)
        for col, key in zip(cols, TOPF_KEYS):
            bucket_metric(col, key, getattr(p, key))
        st.markdown(
            f"<div class='total-line'>Gesamtvermoegen "
            f"<span class='total-value'>{euro(p.gesamt)}</span></div>",
            unsafe_allow_html=True,
        )
    with right:
        fig = donut_chart(p)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("<div class='spacer'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Kernlogik
# ---------------------------------------------------------------------------

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
        "Neues Geld angelegt",
        f"{euro(neues_kapital)} eingezahlt -> Verbrauch: {euro(plan['verbrauchstopf'])}, "
        f"Zins: {euro(plan['zinstopf'])}, Investition: {euro(plan['investitionstopf'])}",
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
    details = "; ".join(
        [f"{FONDS[v]['name']} -> {FONDS[n]['name']}: {euro(b)}" for v, n, b in transfers]
    )
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
        f"Entnommen: {euro(plan['entnahme'])} | Modus: {modus} | "
        f"Aus Zinstopf: {euro(plan['aus_zins'])} | Aus Investitionstopf: {euro(plan['aus_invest'])}",
    )


# ---------------------------------------------------------------------------
# Seiteneinstellungen und Design (CSS)
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Drei-Toepfe-Portfolio", page_icon="◆", layout="wide")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', 'Segoe UI', sans-serif;
        color: {COLORS['primary']};
    }}
    .stApp {{ background: {COLORS['bg']}; }}
    #MainMenu, footer, header {{ visibility: hidden; }}

    /* Kopfbereich */
    .app-header {{
        background: {COLORS['primary']};
        color: #FFFFFF;
        padding: 22px 30px;
        border-radius: 14px;
        margin-bottom: 26px;
    }}
    .app-header h1 {{
        font-size: 1.7rem; font-weight: 700; margin: 0; color: #FFFFFF;
        letter-spacing: -0.3px;
    }}
    .app-header p {{
        margin: 6px 0 0 0; color: #B9C4D6; font-size: 0.98rem;
    }}

    /* Abschnittstitel */
    .section-title {{
        font-size: 1.35rem; font-weight: 600; color: {COLORS['primary']};
        margin: 4px 0 2px 0;
    }}
    .section-sub {{
        color: {COLORS['muted']}; font-size: 0.95rem; margin-bottom: 16px;
    }}

    /* Karten */
    .card {{
        background: {COLORS['card']};
        border: 1px solid {COLORS['line']};
        border-radius: 14px;
        padding: 22px 24px;
        margin-bottom: 18px;
        box-shadow: 0 1px 3px rgba(16,24,40,0.04);
    }}

    /* Kennzahl-Karten */
    .metric-card {{
        background: {COLORS['card']};
        border: 1px solid {COLORS['line']};
        border-radius: 12px;
        padding: 16px 18px 16px 16px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(16,24,40,0.04);
    }}
    .metric-bar {{
        position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
    }}
    .metric-label {{
        color: {COLORS['muted']}; font-size: 0.85rem; font-weight: 500;
        margin-left: 8px;
    }}
    .metric-value {{
        color: {COLORS['primary']}; font-size: 1.35rem; font-weight: 700;
        margin-left: 8px; margin-top: 2px; letter-spacing: -0.5px;
    }}
    .total-line {{
        margin-top: 14px; color: {COLORS['muted']}; font-size: 0.95rem;
        font-weight: 500;
    }}
    .total-value {{
        color: {COLORS['primary']}; font-size: 1.15rem; font-weight: 700;
        margin-left: 8px;
    }}
    .spacer {{ height: 8px; }}

    /* Hinweisboxen */
    .hinweis {{
        background: #FFFFFF;
        border: 1px solid {COLORS['line']};
        border-left: 4px solid {COLORS['accent']};
        border-radius: 8px;
        padding: 14px 18px;
        margin: 10px 0 18px 0;
        color: #374151; font-size: 0.97rem; line-height: 1.5;
    }}

    /* Buttons */
    .stButton > button {{
        background: {COLORS['accent']};
        color: #FFFFFF;
        border: none;
        border-radius: 9px;
        font-size: 1rem;
        font-weight: 600;
        padding: 0.6em 1.6em;
        transition: background 0.15s ease;
    }}
    .stButton > button:hover {{
        background: {COLORS['primary']};
        color: #FFFFFF;
    }}

    /* Eingabefelder */
    div[data-baseweb="input"] input, .stNumberInput input {{
        font-size: 1.02rem;
    }}
    label, .stRadio label {{ font-size: 0.98rem !important; }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 1px solid {COLORS['line']};
    }}
    section[data-testid="stSidebar"] .section-title {{ font-size: 1.05rem; }}

    /* Fusszeile */
    .app-footer {{
        color: {COLORS['muted']}; font-size: 0.85rem;
        border-top: 1px solid {COLORS['line']};
        padding-top: 16px; margin-top: 30px; line-height: 1.5;
    }}

    /* Produktzeile in Anleitungen */
    .todo-row {{
        background: #FFFFFF; border: 1px solid {COLORS['line']};
        border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;
        display: flex; justify-content: space-between; align-items: center;
        font-size: 0.97rem;
    }}
    .todo-amount {{ font-weight: 700; color: {COLORS['primary']}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

p = st.session_state.portfolio

# Kopfbereich
st.markdown(
    """
    <div class='app-header'>
        <h1>Drei-Toepfe-Portfolio</h1>
        <p>Vermoegen ruhig und strukturiert verwalten &nbsp;·&nbsp; 1 Jahr Verbrauch · 3 Jahre Reserve · Rest fuer spaeter</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    section_title("Navigation")
    if not p.setup_abgeschlossen:
        hinweis("Bitte zuerst <b>Einrichten</b> ausfuellen.", "warn")
    schritt = st.radio(
        "Bereich auswaehlen",
        [
            "Uebersicht",
            "Einrichten",
            "Neues Geld anlegen",
            "Rebalancing",
            "Jaehrliche Entnahme",
            "Verlauf",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown(
        f"<div class='metric-label' style='margin-left:0;'>Gesamtvermoegen</div>"
        f"<div class='metric-value' style='margin-left:0;'>{euro(p.gesamt)}</div>",
        unsafe_allow_html=True,
    )
    if p.setup_abgeschlossen:
        st.markdown(
            f"<div style='color:{COLORS['muted']};font-size:0.85rem;margin-top:6px;'>"
            f"Jahresbedarf: {euro(p.jahresverbrauch)}</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Uebersicht / Verstehen
# ---------------------------------------------------------------------------

if schritt == "Uebersicht":
    if p.setup_abgeschlossen:
        section_title("Uebersicht", "Der aktuelle Stand deines Portfolios auf einen Blick.")
        status_uebersicht(p)

    section_title("Das Prinzip", "Drei Toepfe, eine einfache Regel.")
    cols = st.columns(3)
    for col, key in zip(cols, TOPF_KEYS):
        f = FONDS[key]
        with col:
            st.markdown(
                f"""
                <div class='card' style='border-top:4px solid {f['farbe']};'>
                    <div style='font-weight:600;font-size:1.1rem;'>{f['name']}</div>
                    <div style='color:{COLORS['muted']};font-size:0.9rem;margin:4px 0 12px 0;'>{f['kurz']}</div>
                    <div style='font-size:0.95rem;line-height:1.5;'>{f['erklaerung']}</div>
                    <div style='color:{COLORS['muted']};font-size:0.85rem;margin-top:14px;
                         border-top:1px solid {COLORS['line']};padding-top:10px;'>
                         Produkt: {f['produkt']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    section_title("Zielgroessen berechnen")
    beispiel = st.number_input(
        "Wie viel Geld brauchst du ungefaehr pro Jahr?",
        min_value=0.0, value=float(p.jahresverbrauch) if p.jahresverbrauch else 24000.0,
        step=1000.0,
        help="Zum Ausprobieren. Hier wird noch nichts gespeichert.",
    )
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><div class='metric-bar' style='background:{FONDS['verbrauchstopf']['farbe']};'></div>"
                f"<div class='metric-label'>Verbrauchstopf (1 Jahr)</div>"
                f"<div class='metric-value'>{euro(beispiel)}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='metric-bar' style='background:{FONDS['zinstopf']['farbe']};'></div>"
                f"<div class='metric-label'>Zinstopf (3 Jahre)</div>"
                f"<div class='metric-value'>{euro(beispiel * 3)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='metric-bar' style='background:{FONDS['investitionstopf']['farbe']};'></div>"
                f"<div class='metric-label'>Reserve 4 Jahre gesamt</div>"
                f"<div class='metric-value'>{euro(beispiel * 4)}</div></div>", unsafe_allow_html=True)
    hinweis("Grundregel: 1 Jahr sofort verfuegbar, 3 Jahre Reserve, der Rest arbeitet langfristig.", "info")


# ---------------------------------------------------------------------------
# Einrichten
# ---------------------------------------------------------------------------

elif schritt == "Einrichten":
    section_title("Einrichten", "Einmalig die Ausgangswerte hinterlegen.")
    hinweis("Trage ein, wie viel Geld du pro Jahr brauchst und wie viel aktuell in deinen "
            "drei Fonds liegt. Danach kennt die App deine Zielverteilung.", "info")

    jahresverbrauch = st.number_input(
        "Jaehrlicher Geldbedarf aus dem Portfolio",
        min_value=0.0, value=float(p.jahresverbrauch), step=1000.0,
        help="Der Betrag, den du pro Jahr aus dem Depot entnimmst.",
    )

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div style='color:{COLORS['muted']};font-size:0.88rem;'>Ziel Verbrauchstopf</div>"
                f"<div style='font-weight:700;font-size:1.1rem;'>{euro(jahresverbrauch)}</div>", unsafe_allow_html=True)
    c2.markdown(f"<div style='color:{COLORS['muted']};font-size:0.88rem;'>Ziel Zinstopf</div>"
                f"<div style='font-weight:700;font-size:1.1rem;'>{euro(jahresverbrauch * 3)}</div>", unsafe_allow_html=True)
    c3.markdown(f"<div style='color:{COLORS['muted']};font-size:0.88rem;'>Ziel Investitionstopf</div>"
                f"<div style='font-weight:700;font-size:1.1rem;'>Rest</div>", unsafe_allow_html=True)

    st.markdown("<div class='spacer'></div>", unsafe_allow_html=True)
    section_title("Aktuelle Depotwerte")
    st.caption("Schau in deinem Depot nach, wie viel gerade in jedem der drei Fonds liegt.")
    d1, d2, d3 = st.columns(3)
    with d1:
        v = st.number_input("Verbrauchstopf", min_value=0.0, value=float(p.verbrauchstopf), step=500.0)
    with d2:
        z = st.number_input("Zinstopf", min_value=0.0, value=float(p.zinstopf), step=500.0)
    with d3:
        i = st.number_input("Investitionstopf", min_value=0.0, value=float(p.investitionstopf), step=500.0)

    if st.button("Speichern"):
        p.jahresverbrauch = jahresverbrauch
        p.verbrauchstopf = v
        p.zinstopf = z
        p.investitionstopf = i
        p.setup_abgeschlossen = True
        p.log("Einrichtung", f"Jahresverbrauch={euro(jahresverbrauch)}, Verbrauch={euro(v)}, "
                             f"Zins={euro(z)}, Invest={euro(i)}")
        save_portfolio(p)
        st.success("Gespeichert. Du kannst nun mit neuem Geld oder dem Rebalancing fortfahren.")
        st.rerun()


# ---------------------------------------------------------------------------
# Neues Geld anlegen
# ---------------------------------------------------------------------------

elif schritt == "Neues Geld anlegen":
    section_title("Neues Geld anlegen", "Frisches Kapital wird automatisch sinnvoll verteilt.")
    if not p.setup_abgeschlossen:
        hinweis("Bitte zuerst <b>Einrichten</b> ausfuellen.", "warn")
    else:
        status_uebersicht(p)
        hinweis("Neues Geld fuellt zuerst den Verbrauchstopf, dann den Zinstopf und "
                "zuletzt den Investitionstopf.", "info")

        betrag = st.number_input("Anzulegender Betrag", min_value=0.0, value=0.0, step=500.0)
        if betrag > 0:
            plan = kapitalzufuhr_plan(p, betrag)
            section_title("Empfohlene Verteilung")
            for key in TOPF_KEYS:
                f = FONDS[key]
                st.markdown(
                    f"<div class='todo-row'><span><b>{f['name']}</b> "
                    f"<span style='color:{COLORS['muted']};'>· {f['produkt']}</span></span>"
                    f"<span class='todo-amount'>{euro(plan[key])}</span></div>",
                    unsafe_allow_html=True,
                )
            if st.button("Verbuchung bestaetigen"):
                kapitalzufuhr_anwenden(p, plan, betrag)
                save_portfolio(p)
                st.success("Verbucht. Bitte dieselben Kaeufe auch im echten Depot ausfuehren.")
                st.rerun()


# ---------------------------------------------------------------------------
# Rebalancing
# ---------------------------------------------------------------------------

elif schritt == "Rebalancing":
    section_title("Rebalancing", "Die Toepfe wieder in die Zielverteilung bringen.")
    if not p.setup_abgeschlossen:
        hinweis("Bitte zuerst <b>Einrichten</b> ausfuellen.", "warn")
    else:
        hinweis("Wachsen die Toepfe unterschiedlich stark, passt die Verteilung nicht mehr. "
                "Trage die aktuellen Depotwerte ein – die App zeigt, was umgeschichtet werden sollte.", "info")

        c1, c2, c3 = st.columns(3)
        with c1:
            v_ist = st.number_input("Verbrauchstopf", min_value=0.0, value=float(p.verbrauchstopf), step=500.0, key="rv")
        with c2:
            z_ist = st.number_input("Zinstopf", min_value=0.0, value=float(p.zinstopf), step=500.0, key="rz")
        with c3:
            i_ist = st.number_input("Investitionstopf", min_value=0.0, value=float(p.investitionstopf), step=500.0, key="ri")

        if st.button("Werte uebernehmen und berechnen"):
            p.verbrauchstopf, p.zinstopf, p.investitionstopf = v_ist, z_ist, i_ist
            save_portfolio(p)
            st.rerun()

        st.markdown("<div class='spacer'></div>", unsafe_allow_html=True)
        status_uebersicht(p)

        ziel, ist, diff, transfers = rebalancing_plan(p)
        df = pd.DataFrame({
            "Topf": [FONDS[k]["name"] for k in ziel],
            "Ist": [ist[k] for k in ziel],
            "Soll": [ziel[k] for k in ziel],
            "Abweichung": [diff[k] for k in ziel],
        })
        st.dataframe(
            df.style.format({
                "Ist": euro,
                "Soll": euro,
                "Abweichung": lambda x: ("+" if x >= 0 else "") + euro(x),
            }),
            use_container_width=True,
            hide_index=True,
        )

        section_title("Empfohlene Umschichtungen")
        if not transfers:
            hinweis("Alles im gruenen Bereich – es ist keine Umschichtung noetig.", "good")
        else:
            for von, nach, betrag in transfers:
                st.markdown(
                    f"<div class='todo-row'><span>Verkaufe <b>{FONDS[von]['name']}</b> "
                    f"&nbsp;→&nbsp; kaufe <b>{FONDS[nach]['name']}</b></span>"
                    f"<span class='todo-amount'>{euro(betrag)}</span></div>",
                    unsafe_allow_html=True,
                )
            if st.button("Rebalancing verbuchen"):
                rebalancing_anwenden(p, transfers)
                save_portfolio(p)
                st.success("Verbucht. Bitte dieselben Umschichtungen auch im echten Depot ausfuehren.")
                st.rerun()


# ---------------------------------------------------------------------------
# Jaehrliche Entnahme
# ---------------------------------------------------------------------------

elif schritt == "Jaehrliche Entnahme":
    section_title("Jaehrliche Entnahme", "Geld fuer das laufende Jahr entnehmen und auffuellen.")
    if not p.setup_abgeschlossen:
        hinweis("Bitte zuerst <b>Einrichten</b> ausfuellen.", "warn")
    else:
        status_uebersicht(p)
        hinweis("Einmal pro Jahr wird aus dem Verbrauchstopf entnommen. Aufgefuellt wird im "
                "Normalfall aus dem Investitionstopf. In einer Boersenkrise stattdessen aus dem "
                "Zinstopf – so muessen keine Aktien zu schlechten Kursen verkauft werden.", "info")

        krise = st.checkbox("Die Aktienmaerkte sind gerade in einer Krise")
        plan = entnahme_plan(p, krise)

        if p.verbrauchstopf >= p.jahresverbrauch:
            hinweis("Der Verbrauchstopf reicht fuer die geplante Jahresentnahme aus.", "good")
        else:
            hinweis("Der Verbrauchstopf reicht nicht vollstaendig aus. Unten steht, wie aufgefuellt wird.", "warn")

        section_title("Ablauf")
        rows = [
            ("Geplanter Jahresbedarf", euro(p.jahresverbrauch)),
            ("Aktuell im Verbrauchstopf", euro(p.verbrauchstopf)),
            ("Jetzt entnehmen", euro(plan["entnahme"])),
        ]
        for label, val in rows:
            st.markdown(
                f"<div class='todo-row'><span>{label}</span>"
                f"<span class='todo-amount'>{val}</span></div>",
                unsafe_allow_html=True,
            )

        if plan["aus_zins"] > 0.01:
            st.markdown(f"<div class='todo-row'><span>Aus Zinstopf in Verbrauchstopf umschichten</span>"
                        f"<span class='todo-amount'>{euro(plan['aus_zins'])}</span></div>", unsafe_allow_html=True)
        if plan["aus_invest"] > 0.01:
            st.markdown(f"<div class='todo-row'><span>Aus Investitionstopf verkaufen</span>"
                        f"<span class='todo-amount'>{euro(plan['aus_invest'])}</span></div>", unsafe_allow_html=True)
            if plan["an_verbrauch"] > 0.01:
                st.markdown(f"<div class='todo-row'><span>&nbsp;&nbsp;davon in Verbrauchstopf</span>"
                            f"<span class='todo-amount'>{euro(plan['an_verbrauch'])}</span></div>", unsafe_allow_html=True)
            if plan["an_zins"] > 0.01:
                st.markdown(f"<div class='todo-row'><span>&nbsp;&nbsp;davon in Zinstopf</span>"
                            f"<span class='todo-amount'>{euro(plan['an_zins'])}</span></div>", unsafe_allow_html=True)

        if plan["aus_zins"] <= 0.01 and plan["aus_invest"] <= 0.01:
            hinweis("Es ist keine weitere Umschichtung noetig.", "info")

        if st.button("Entnahme verbuchen"):
            entnahme_anwenden(p, plan)
            save_portfolio(p)
            st.success("Verbucht. Bitte dieselben Verkaeufe/Kaeufe auch im echten Depot ausfuehren.")
            st.rerun()


# ---------------------------------------------------------------------------
# Verlauf
# ---------------------------------------------------------------------------

elif schritt == "Verlauf":
    section_title("Verlauf", "Alle bisherigen Aktionen im Ueberblick.")
    if p.history:
        df_hist = pd.DataFrame(p.history[::-1])
        for spalte in ["Verbrauchstopf", "Zinstopf", "Investitionstopf"]:
            if spalte in df_hist.columns:
                df_hist[spalte] = df_hist[spalte].apply(euro)
        st.dataframe(df_hist, use_container_width=True, height=420, hide_index=True)

        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=p.history[0].keys())
        writer.writeheader()
        writer.writerows(p.history)
        st.download_button(
            "Verlauf als CSV herunterladen",
            data=csv_buf.getvalue(),
            file_name="portfolio_verlauf.csv",
            mime="text/csv",
        )
    else:
        hinweis("Noch kein Verlauf vorhanden.", "info")


# ---------------------------------------------------------------------------
# Fusszeile
# ---------------------------------------------------------------------------

st.markdown(
    "<div class='app-footer'>Diese Anwendung fuehrt keine echten Banktransaktionen aus. "
    "Sie dient ausschliesslich der Planung und zeigt, welche Schritte im echten Depot "
    "auszufuehren sind. Grundregel: 1 Jahr Verbrauchstopf, 3 Jahre Zinstopf, der Rest im "
    "Investitionstopf.</div>",
    unsafe_allow_html=True,
)
