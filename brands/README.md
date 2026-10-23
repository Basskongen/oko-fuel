# Ikon for integrasjonsvelgeren

Home Assistant henter ikonet til alle integrasjoner fra det sentrale registeret
[brands.home-assistant.io](https://brands.home-assistant.io), ikke fra integrasjonen selv.
Fram til ikonet er godkjent der viser HA et generisk plassholderikon. Integrasjonen virker
uansett.

`icon.svg` er kilden. `oko_fuel/icon.png` (256×256) og `oko_fuel/icon@2x.png`
(512×512) er rendret fra den, med gjennomsiktig bakgrunn utenfor den avrundede firkanten.

## Sende inn til brands-registeret

1. Fork <https://github.com/home-assistant/brands> på GitHub.
2. Opprett mappa `custom_integrations/oko_fuel/` i forken (merk: `custom_integrations`,
   ikke `core_integrations`).
3. Legg `icon.png` og `icon@2x.png` fra `brands/oko_fuel/` her i den mappa.
4. Lag en pull request mot `master`. Tittel: `Add oko_fuel custom integration`.
   I beskrivelsen: lenke til dette repoet og «Icon is based on Material Design Icons
   gas-station (Apache 2.0)».
5. Godkjenning tar vanligvis noen dager. Ikonet dukker da opp i HA av seg selv, uten
   at integrasjonen må oppdateres (nettleseren kan trenge en hard oppdatering).

Krav fra registeret som disse filene oppfyller: PNG, kvadratisk, 256 px og 512 px,
gjennomsiktig bakgrunn tillatt, ingen logo-fil siden den ville vært identisk med ikonet.

## Regenerere PNG fra SVG

```bash
npx -y -p sharp node -e "const s=require('sharp');s('brands/icon.svg',{density:300}).resize(256,256).png().toFile('brands/oko_fuel/icon.png');s('brands/icon.svg',{density:300}).resize(512,512).png().toFile('brands/oko_fuel/icon@2x.png')"
```
