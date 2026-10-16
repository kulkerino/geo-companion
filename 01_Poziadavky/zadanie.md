# Zadanie projektu: Geo Companion

## Cieľ projektu

Geo Companion je aplikácia, ktorej **jadrom je vlastný model na rozpoznávanie krajiny z fotky**.
Používateľ nahrá fotku alebo snímku obrazovky (napr. z hry GeoGuessr) a model odhadne,
z ktorej krajiny je, s akou istotou, a podľa akých znakov (stĺpiky pri ceste, ŠPZ, písmo,
strana jazdy a podobne).

Okolo modelu je postavená aplikácia, v ktorej sa používateľ môže sám učiť krajiny spoznávať
a porovnať sa s modelom.

## Čo bude aplikácia robiť

- **Rozpoznanie krajiny z fotky:** 3 najpravdepodobnejšie krajiny s percentom istoty a nájdené znaky (meta).
- **Tréning hádania:** aplikácia ukáže fotku, používateľ tipne krajinu a potom vidí správnu odpoveď a vysvetlenie.
- **Preteky s modelom:** používateľ aj model tipnú tú istú fotku, potom sa odhalia oba tipy aj správna odpoveď.
- **Presnosť modelu:** poctivo nameraná na testovacích fotkách, ktoré model pri trénovaní nevidel.
- **Pokrok:** aplikácia ukladá výsledky používateľa.

## Rozsah

- Všetky krajiny dostupné v GeoGuessr (približne 120). Najprv krajina, neskôr regióny vo veľkých krajinách (Brazília, Rusko, Japonsko).
- Model sa trénuje od začiatku (from scratch) na stolnom počítači s grafickou kartou RTX 3060. Ak výsledky nebudú dobré, použije sa predtrénovaný model.
- Fotky na trénovanie: verejné datasety (Mapillary, OSV-5M). Žiadne automatické sťahovanie z Google Street View.
- Aplikácia zobrazuje len fotky, ktoré sa smú použiť, vždy s autorom a licenciou.
- Aplikácia funguje aj bez internetu; odhad modelu vyžaduje dostupný stolný počítač v domácej sieti.
- Rozhranie v angličtine s možnosťou slovenčiny.

## Čo aplikácia robiť nebude

- Nebude pomáhať počas prebiehajúcej hry GeoGuessr.
- Nebude mať používateľské účty ani nebude verejnou webovou stránkou.
- Nebude posielať fotky používateľa mimo domácej siete.

## Cieľ presnosti

Model má byť jasne lepší ako náhodný tip, napríklad správna krajina medzi top 3 tipmi
vo viac ako 60 % testovacích fotiek.

## Termín

Funkčná verzia s ukážkou v škole: február 2027.

## Súvisiace dokumenty

- [Role systému](role-systemu.xlsx)
- [Funkcionálne požiadavky](funkcionalne-poziadavky.xlsx)
- [Nefunkcionálne požiadavky](nefunkcionalne-poziadavky.xlsx)
- [Prípady použitia](../02_Analyza/use-case.docx)
