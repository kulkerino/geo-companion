# Geo Companion

Ročníkový projekt: aplikácia, ktorej **jadrom je vlastný model na rozpoznávanie krajiny z fotky**.
Okolo modelu je postavený tréning hádania krajín a preteky s modelom.

| | |
|---|---|
| **Názov projektu** | Geo Companion |
| **Autor** | Adam Kovac & Ondrej Kocian |
| **Trieda** | *BTL* |
| **Vyučujúci** | Roman Janega |
| **Školský rok** | 2026/2027 |

## Cieľ projektu

Používateľ nahrá fotku alebo snímku obrazovky a model odhadne 3 najpravdepodobnejšie krajiny
s percentom istoty a ukáže, podľa akých znakov (stĺpiky, ŠPZ, písmo, strana jazdy) sa rozhodol.
V tréningu sa používateľ učí krajiny spoznávať sám a v pretekoch sa porovná s modelom.
Presnosť modelu sa meria poctivo na fotkách, ktoré model pri trénovaní nevidel.
Podrobnosti sú v [zadaní](01_Poziadavky/zadanie.md).

## Aktuálny stav (16. 10. 2026)

- Hotové: tréning hádania (fotka bez prezradenia krajiny, tip, odhalenie s vysvetlením,
  preskočenie, nahlásenie, opakovanie), ukladanie pokroku, porovnanie so zástupným modelom.
- Vo vývoji: zber dát a trénovanie skutočného modelu, nahranie vlastnej fotky, preteky s modelom,
  prehľad presnosti.

## Postup spustenia aplikácie

Potrebný softvér: Python 3.12 s nástrojom uv, Node.js 24 s pnpm. Podrobne v
[inštalačnej príručke](06_Dokumentacia/instalacna-prirucka.docx).

```
cd 04_Implementacia/src
uv sync --python 3.12 --all-groups
pnpm install --frozen-lockfile
uv run uvicorn geo_companion.main:app --host 127.0.0.1 --port 8000
pnpm --dir apps/web dev        # v druhom termináli
```

Potom otvoriť v prehliadači **http://127.0.0.1:5173**. Aplikácia nemá prihlasovanie ani heslá.

## Štruktúra projektu

| Priečinok | Obsah |
|---|---|
| [01_Poziadavky](01_Poziadavky) | zadanie, role systému, funkcionálne a nefunkcionálne požiadavky |
| [02_Analyza](02_Analyza) | use case diagram a scenáre prípadov použitia |
| [03_Navrh](03_Navrh) | ERD, schéma databázy, architektúra a náčrty obrazoviek |
| [04_Implementacia/src](04_Implementacia/src) | zdrojový kód aplikácie (Python FastAPI + React) |
| [05_Testovanie](05_Testovanie) | testovacie scenáre a zistené chyby |
| [06_Dokumentacia](06_Dokumentacia) | používateľská a inštalačná príručka |
