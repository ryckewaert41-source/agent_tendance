#!/usr/bin/env python3
"""
Agent tendance : calcule chaque jour l'état de tendance d'un panier de cryptos, de paires forex et d'actions,
puis écrit docs/data/tendances.json, lu par la page web docs/index.html.

Trois signaux, aux paramètres fixés d'avance (ce sont ceux de nos tests) :
  - croisement : SMA 20 jours au-dessus de SMA 50 jours (+1) ou en dessous (-1)
  - cassure    : cassure du plus haut (+1) ou du plus bas (-1) des 20 derniers jours, gardée jusqu'à la cassure inverse
  - momentum   : prix en hausse (+1) ou en baisse (-1) sur 60 jours
Score = somme des trois signaux (de -3 à +3). Haussière si score >= 2, baissière si <= -2, sinon mixte.

Utilisation :  python agent_tendance.py          (données réelles via Yahoo Finance)
               python agent_tendance.py --demo   (données simulées, pour tester sans internet)
Seules les bougies journalières COMPLÈTES (datées d'avant aujourd'hui, UTC) sont utilisées.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent
UNIVERS = RACINE / "univers.json"
SORTIE = RACINE / "docs" / "data" / "tendances.json"
MIN_BOUGIES = 120          # historique minimal pour calculer les trois signaux
POINTS_GRAPHIQUE = 90      # nombre de clôtures envoyées pour le mini-graphique
JOURS_EVENEMENTS = 30      # fenêtre des changements récents affichés


# ----------------------------- Données -----------------------------
def telecharger(symbole, essais=3):
    import yfinance as yf
    derniere = "échec"
    for i in range(essais):
        try:
            df = yf.Ticker(symbole).history(period="3y", interval="1d", auto_adjust=True)
            if df is not None and len(df):
                df = df.rename(columns=str.lower)[["open", "high", "low", "close"]].dropna()
                df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
                return df
            derniere = "aucune donnée reçue"
        except Exception as e:                       # réseau, limite de requêtes, symbole inconnu...
            derniere = str(e)[:120] or "erreur inconnue"
        time.sleep(2 * (i + 1))
    raise RuntimeError(derniere)


def simuler(symbole, jours=420):
    """Données simulées (déterministes) pour tester la chaîne sans internet."""
    graine = int(hashlib.sha1(symbole.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(graine)
    vol = 0.03 if symbole.endswith("-USD") else 0.004 if symbole.endswith("=X") else 0.012
    rend = rng.normal(0.0003, vol, jours)
    for i in range(1, jours):
        rend[i] += 0.08 * rend[i - 1]               # un peu de tendance
    close = 100 * np.exp(np.cumsum(rend))
    fin = pd.Timestamp(datetime.now(timezone.utc).date()) - pd.Timedelta(days=1)
    idx = pd.date_range(end=fin, periods=jours, freq="D")
    ouvert = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": ouvert, "high": np.maximum(ouvert, close) * 1.004,
                         "low": np.minimum(ouvert, close) * 0.996, "close": close}, index=idx)


# ----------------------------- Analyse -----------------------------
def signaux(df):
    close, haut, bas = df["close"], df["high"], df["low"]
    sma20, sma50 = close.rolling(20).mean(), close.rolling(50).mean()
    croisement = pd.Series(np.where(sma20 > sma50, 1, -1), index=df.index)
    croisement[sma50.isna()] = 0

    plus_haut = haut.rolling(20).max().shift(1)
    plus_bas = bas.rolling(20).min().shift(1)
    brut = np.where(close > plus_haut, 1.0, np.where(close < plus_bas, -1.0, np.nan))
    cassure = pd.Series(brut, index=df.index).ffill().fillna(0)

    momentum = np.sign(close / close.shift(60) - 1).fillna(0)
    sig = pd.DataFrame({"croisement": croisement, "cassure": cassure, "momentum": momentum}).astype(int)
    score = sig.sum(axis=1)
    etat = pd.Series(np.select([score >= 2, score <= -2], [1, -1], 0), index=df.index)
    return sig, score, etat, sma20, sma50


def analyser(symbole, nom, classe, df):
    aujourdhui = pd.Timestamp(datetime.now(timezone.utc).date())
    df = df[df.index < aujourdhui]                      # on ne garde que les bougies complètes
    if len(df) < MIN_BOUGIES:
        raise RuntimeError(f"historique trop court ({len(df)} bougies)")
    sig, score, etat, sma20, sma50 = signaux(df)
    close = df["close"]
    tr = pd.concat([df["high"] - df["low"], (df["high"] - close.shift()).abs(),
                    (df["low"] - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()

    valides = np.arange(len(df)) >= 60                  # avant, le momentum n'est pas défini
    changements = [i for i in range(61, len(df)) if etat.iloc[i] != etat.iloc[i - 1]]
    depuis = int(len(df) - 1 - changements[-1]) if changements else None
    limite = len(df) - JOURS_EVENEMENTS
    evenements = [dict(date=df.index[i].strftime("%Y-%m-%d"), symbole=symbole, nom=nom, classe=classe,
                       de=int(etat.iloc[i - 1]), vers=int(etat.iloc[i])) for i in changements if i >= limite]

    def variation(n):
        return float(close.iloc[-1] / close.iloc[-1 - n] - 1) * 100 if len(close) > n else None

    arrondi = lambda x: float(f"{x:.6g}")
    actif = dict(
        symbole=symbole, nom=nom, classe=classe, erreur=None,
        derniere_bougie=df.index[-1].strftime("%Y-%m-%d"), prix=arrondi(close.iloc[-1]),
        var_1j=variation(1), var_7j=variation(7), var_30j=variation(30),
        ecart_sma50=float(close.iloc[-1] / sma50.iloc[-1] - 1) * 100,
        atr_pct=float(atr.iloc[-1] / close.iloc[-1]) * 100,
        signaux={k: int(v) for k, v in sig.iloc[-1].items()}, score=int(score.iloc[-1]), etat=int(etat.iloc[-1]),
        jours_depuis_changement=depuis,
        graphique=[arrondi(x) for x in close.iloc[-POINTS_GRAPHIQUE:]],
    )
    return actif, evenements


# ----------------------------- Programme -----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="données simulées, sans internet")
    args = parser.parse_args()

    univers = json.loads(UNIVERS.read_text(encoding="utf-8"))["classes"]
    actifs, evenements, erreurs = [], [], 0
    for classe, bloc in univers.items():
        for item in bloc["symboles"]:
            s, nom = item["symbole"], item["nom"]
            try:
                df = simuler(s) if args.demo else telecharger(s)
                actif, evts = analyser(s, nom, classe, df)
                actifs.append(actif)
                evenements.extend(evts)
                print(f"  {s:<10} {nom:<22} score {actif['score']:+d}  dernière bougie {actif['derniere_bougie']}")
            except Exception as e:
                erreurs += 1
                actifs.append(dict(symbole=s, nom=nom, classe=classe, erreur=str(e)))
                print(f"  {s:<10} ERREUR : {e}")

    total = len(actifs)
    if erreurs > total / 2:
        sys.exit(f"Trop d'erreurs ({erreurs}/{total}) : le fichier existant est conservé.")

    evenements.sort(key=lambda e: (e["date"], e["symbole"]), reverse=True)
    sortie = dict(
        genere_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), demo=bool(args.demo),
        classes={c: dict(titre=b["titre"], note=b["note"]) for c, b in univers.items()},
        actifs=actifs, changements=evenements[:60],
    )
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n{total - erreurs}/{total} actifs analysés -> {SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
