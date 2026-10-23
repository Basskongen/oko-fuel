# Øko-fuel – norske drivstoffpriser i Home Assistant

Drivstoffpriser per bensinstasjon i Home Assistant, hentet fra det åpne API-et til
[drivstoffapp.no](https://backend.drivstoffapp.no/docs). Ingen nøkkel, ingen innlogging,
ingen YAML.

Du velger et område på kartet, krysser av stasjonene du vil følge, og får:

- én prissensor per stasjon og drivstofftype (bensin 95, bensin 98, diesel, HVO100,
  farget diesel, E10), f.eks. `sensor.circle_k_tynset_diesel`
- en «Billigste …»-sensor per drivstofftype, med hvilken stasjon som er billigst
  og en rangering av alle stasjonene i attributtene
- «Sist oppdatert»-tidsstempel per stasjon

Prisene er i NOK/L og oppdateres hvert 30. minutt (kan endres).

## Installasjon via HACS (anbefalt)

[![Åpne repoet i HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Basskongen&repository=oko-fuel&category=integration)

Eller manuelt:

1. Åpne **HACS** i Home Assistant.
2. Klikk de tre prikkene øverst til høyre → **Custom repositories**.
3. Lim inn `https://github.com/Basskongen/oko-fuel`, velg type **Integration**, klikk **Add**.
4. Søk opp **Øko-fuel** i HACS og klikk **Download**.
5. Start Home Assistant på nytt.

### Uten HACS

Kopier mappa `custom_components/oko_fuel` inn i `config/custom_components/`
på Home Assistant-maskinen (f.eks. via Samba eller File editor) og start på nytt.

## Oppsett

1. **Innstillinger → Enheter og tjenester → Legg til integrasjon**, søk **Øko-fuel**.
2. **Steg 1 – område:** et kart med en sirkel dukker opp, forhåndsutfylt med
   hjemmeposisjonen din. Flytt markøren og dra i sirkelkanten for å endre radius
   (standard 10 km, maks 100 km).
3. **Steg 2 – stasjoner:** du får en liste over alle stasjonene i området med navn og
   adresse. Kryss av de du vil følge, og hvilke drivstofftyper du bryr deg om.
4. Ferdig. Hver stasjon blir en egen enhet med sine prissensorer.

Vil du legge til eller fjerne stasjoner senere, eller endre oppdateringsintervall:
åpne integrasjonen og klikk **Konfigurer**.

Flere områder (f.eks. hjemme og hytta)? Legg til integrasjonen én gang til.

## Eksempel på bruk

Varsel når diesel faller under 25 kr på billigste stasjon:

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.oko_fuel_tynset_billigste_diesel
    below: 25
actions:
  - action: notify.mobile_app_telefon
    data:
      message: >-
        Diesel {{ states('sensor.oko_fuel_tynset_billigste_diesel') }} kr
        hos {{ state_attr('sensor.oko_fuel_tynset_billigste_diesel', 'station_name') }}
```

## Alternativ uten integrasjon

Vil du heller ha rene YAML-sensorer (`rest:`), se
[`examples/rest_sensor.yaml`](examples/rest_sensor.yaml). Det krever at du finner
stasjons-ID-ene selv og redigerer YAML, men trenger ingen HACS.

## Forbehold

- API-et er uoffisielt (ingen avtale om oppetid eller at formatet holder seg).
  Integrasjonen gjør ett kall per oppdatering uansett antall stasjoner, så den
  belaster tjenesten lite.
- Dekningen varierer. Noen stasjoner mangler priser eller har gamle priser; sjekk
  «Sist oppdatert»-sensoren.
- Feltet «Bensin 98» tilsvarer API-ets `octane_price`. Hos enkelte stasjoner ser
  tallet merkelig lavt ut, så bruk det med litt skepsis.
- Ikonet ligger i `custom_components/oko_fuel/brand/` og vises av Home Assistant
  2026.3 eller nyere. Eldre versjoner viser et plassholderikon. Kilden er
  [`assets/icon.svg`](assets/icon.svg).

## Utvikling

```bash
pip install pytest-homeassistant-custom-component
pytest
```
