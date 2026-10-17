# ha-madeira-fuel-prices

A [Home Assistant](https://www.home-assistant.io/) custom integration with the weekly **maximum fuel prices in
Madeira** (Portugal), as published in [JORAM](https://joram.madeira.gov.pt), the official journal of the
Autonomous Region of Madeira.

The Regional Government sets the maximum retail prices every week. The order is published in JORAM, usually on
a Thursday or Friday, and applies from 0:00 on the following Monday. The journal offers no data feed for these
prices, so the project behind <https://madeirafuelprices.fyi/> reads each order once and publishes it as a small
JSON file, which this integration fetches.

This is an unofficial project, not affiliated with the Regional Government. The journal is the authority; check
it if a price matters.

## Features

- Sensors for the prices in force today: petrol 95, road diesel, and coloured (agricultural) diesel, in €/L.
- Sensors for next week's prices, as soon as the order is published (`unknown` until then).
- The date the current prices started and the date the next ones start.
- Prices switch to the new order at 0:00 in Madeira on the day it starts, without waiting for the next fetch.
- Each sensor carries the journal issue it came from (`source`, `source_url`) and the Portaria the order cites
  (`portaria`).
- Two diagnostic sensors tell you whether the data can be trusted: when it last changed, and how many warnings
  came with it.
- Known prices are kept across restarts and while the feed is unreachable.

## Sensors

| Entity | Meaning |
|---|---|
| `sensor.madeira_fuel_prices_petrol_95` | Petrol 95, price in force |
| `sensor.madeira_fuel_prices_diesel` | Road diesel, price in force |
| `sensor.madeira_fuel_prices_coloured_diesel` | Coloured and marked diesel, price in force |
| `sensor.madeira_fuel_prices_valid_from` | Date the prices in force started |
| `sensor.madeira_fuel_prices_next_petrol_95` | Petrol 95, next order |
| `sensor.madeira_fuel_prices_next_diesel` | Road diesel, next order |
| `sensor.madeira_fuel_prices_next_coloured_diesel` | Coloured and marked diesel, next order |
| `sensor.madeira_fuel_prices_next_valid_from` | Date the next order starts |
| `sensor.madeira_fuel_prices_data_updated` | When the published data last changed |
| `sensor.madeira_fuel_prices_warnings` | Number of warnings that came with the data; the `codes` and `messages` attributes list them |

In a normal week the data changes on Friday or Saturday and again on Monday. To be told when something is wrong,
notify when `data_updated` is more than 8 days old or `warnings` is above 0. The warning codes are listed in
[docs/feed.md](docs/feed.md#warnings).

## Installation

### HACS (recommended)

1. In Home Assistant, open **HACS**.
2. Select the three-dot menu → **Custom repositories**.
3. Add `https://github.com/hanunes/ha-madeira-fuel-prices` with category **Integration**.
4. Install **Madeira Fuel Prices**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/madeira_fuel_prices` folder into your Home Assistant `config/custom_components`
   directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Madeira Fuel Prices** and follow the prompts.

There is nothing to set. Only a single instance of the integration is supported.

## How it works

- Once an hour the integration fetches one small file,
  `https://madeirafuelprices.fyi/api/v1/prices.json`, which holds the order in force and the next one. A job
  there reads JORAM once a day. The file's format is described in [docs/feed.md](docs/feed.md).
- The order in force is worked out from each order's start date and today's date in Madeira
  (`Atlantic/Madeira`), whatever Home Assistant's own time zone is.
- The last valid copy of the file is kept. A fetch that fails, or an answer that is not valid, changes nothing.

## Troubleshooting

- **Setup keeps retrying, "could not fetch the price feed"**: the feed did not answer and no prices are known
  yet. Setup tries again by itself.
- **Prices look out of date**: check the `data_updated` and `warnings` sensors. If the data is more than 8 days
  old and there is no `no_new_order` warning, the job that reads JORAM has probably stopped; please open an
  issue.
- For more detail, enable debug logging for `custom_components.madeira_fuel_prices`.

## Development

```sh
pip install -r requirements_test.txt
pytest
```

The feed's format and the rules for reading it are in [docs/feed.md](docs/feed.md).

## License

MIT
