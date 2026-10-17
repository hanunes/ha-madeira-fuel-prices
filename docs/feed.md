# The price feed

This integration reads its prices from a small JSON feed instead of reading JORAM itself. This page describes
that feed: where it is, what it holds, how it behaves over a week, and what the integration does with it.

Up to version 0.1.0 the integration downloaded and parsed the journal's PDFs itself. Since 0.2.0 it reads only
the feed (`api.py`).

## Where it is

```
GET https://madeirafuelprices.fyi/api/v1/prices.json
```

The feed is one static file, published by the project `madeira-fuel-prices` (a separate, private repository). A
job there reads JORAM once a day, and the file is written again only when its content changes. The same project
publishes the pages at <https://madeirafuelprices.fyi/>.

The point of the feed is that one job reads JORAM for everyone, instead of every Home Assistant install doing it.

- This is the only address. There is no fallback address; when a fetch fails, the integration keeps the values it
  has.
- No key and no sign-in.
- The answer is `application/json` in UTF-8, with an `ETag`, and `Cache-Control: public, max-age=0,
  must-revalidate`. A request with `If-None-Match` gets `304` when nothing changed.
- `Access-Control-Allow-Origin: *` is set, so a browser can read it too.

## What it holds

```json
{
  "updated_at": "2026-10-03T14:40:25Z",
  "warnings": [],
  "current": {
    "valid_from": "2026-09-28",
    "petrol_95": 2.029,
    "diesel": 2.148,
    "coloured_diesel": 1.7,
    "portaria": "25/2022",
    "source": "https://joram.madeira.gov.pt/joram/2serie/Ano%20de%202026/IISerie-174-2026-09-25Supl3.pdf"
  },
  "next": {
    "valid_from": "2026-10-05",
    "petrol_95": 2.021,
    "diesel": 2.12,
    "coloured_diesel": 1.672,
    "portaria": "25/2022",
    "source": "https://joram.madeira.gov.pt/joram/2serie/Ano%20de%202026/IISerie-179-2026-10-02Supl.pdf"
  }
}
```

### Top level

| Field | Type | Meaning |
|---|---|---|
| `updated_at` | string | When the file's content last changed, in UTC, as `YYYY-MM-DDTHH:MM:SSZ`. It is not the time of the last run: a run that finds nothing new leaves the file as it is. |
| `warnings` | array | What the last run that changed the file found wrong. Empty when all is well. See [Warnings](#warnings). |
| `current` | order or `null` | The order in force on the day the file was written. `null` only if no order has ever been read. |
| `next` | order or `null` | The order that follows it. `null` until that order is published. |

### An order

| Field | Type | Meaning |
|---|---|---|
| `valid_from` | string | The day the order comes into force, as `YYYY-MM-DD`. It starts at 0:00 that day in Madeira (`Atlantic/Madeira`). |
| `petrol_95` | number or `null` | Maximum price of petrol 95, in euros per litre. |
| `diesel` | number or `null` | Maximum price of road diesel, in euros per litre. |
| `coloured_diesel` | number or `null` | Maximum price of coloured and marked diesel, in euros per litre. |
| `portaria` | string or `null` | The Portaria the order cites as its legal basis, for example `"25/2022"`. |
| `source` | string | The address of the JORAM issue (a PDF) the order was read from. |

- An order has no end date. It stays in force until the next one starts, which is normally 7 days later but can
  be 14 or more in a week when no order is published.
- A price is `null` when it could not be read from the order; a `fuel_missing` warning comes with it. In practice
  only `coloured_diesel` can be `null`: an order without petrol 95 or road diesel is not recognised as an order
  at all. Prices outside 0.50 to 5.00 euros per litre are treated as misread and left out in the same way.
- Prices have at most three decimals. They are JSON numbers, so `1.700` arrives as `1.7`.

## How it changes over a week

The Regional Government publishes the order on a Friday (sometimes a Thursday), and it comes into force at 0:00
on the following Monday.

| When | What changes in the file |
|---|---|
| The morning after the order is published (the daily run is at 06:17 UTC) | `next` goes from `null` to the new order. |
| Monday, shortly after 0:00 in Madeira | The new order moves to `current`, and `next` becomes `null`. |
| Any day | `warnings` changes when a warning appears or clears. |

On other days the file does not change, and `updated_at` stays as it was.

### `current` can be a few hours behind on Monday

`current` and `next` are worked out when the job runs, for that day's date in Madeira. The Monday run is
scheduled just after midnight, but GitHub starts scheduled jobs late. On Monday 5 October 2026 the file changed at
01:43 UTC, 2 hours 43 minutes after midnight in Madeira; until then `current` was still the order of the week
before, and the order already in force was under `next`.

So the integration must not take `current` as "in force now". It works out the order in force itself:

1. Take the orders in `current` and `next` that are not `null`.
2. The order in force is the one with the latest `valid_from` that is not after today's date in Madeira.
3. An order whose `valid_from` is after today is the next one. If there is none, the next order is not known yet.

This also makes the prices switch at 0:00 on Monday without a fetch.

## Warnings

A warning is an object with a `code` and a `message`:

```json
{ "code": "no_new_order", "message": "No order has been found for the week of 2026-10-12." }
```

The `message` is in English and written for a person; its wording may change. The `code` is stable.

| Code | Meaning |
|---|---|
| `joram_unreachable` | JORAM's list of issues could not be read. The orders stay as they were. |
| `issue_unreadable` | One or more issues could not be downloaded or read. What could be read was published. |
| `no_new_order` | No order for the coming week by Saturday, five days after the last one started. |
| `no_orders` | No order has ever been read. `current` and `next` are `null`. |
| `fuel_missing` | An order shown in the file lacks a fuel's price. |
| `portaria_missing` | An order shown in the file names no Portaria that could be read. |
| `other_portaria` | An order shown in the file cites a Portaria other than 25/2022. |
| `price_jump` | A fuel changes by more than 0.30 euros per litre from the order before it. |

- The job never holds back what it read: a doubtful order is published together with its warning.
- Only the orders in the file are checked, so a warning about an order clears when that order is no longer shown.
- More codes may be added. A code the integration does not know is still a warning.

## How old the data is

`updated_at` is the only sign of whether the job is alive. In a normal week the file changes on Friday or Saturday
and again on Monday, so it is never more than about five days old.

A file more than 8 days old means one of two things:

- The job has stopped running, or its runs are failing before they write anything. `warnings` cannot say so,
  since nothing is writing the file.
- No order was published for a week. Then `no_new_order` is in `warnings`, and the last order is still in force.

## What stays the same

The `v1` in the address is the format's version.

- Fields of `v1` are not removed or renamed, and their types do not change.
- New fields may be added, at the top level or in an order (a "last checked" time has been considered). The
  integration ignores fields it does not know.
- New warning codes may be added.
- A change that breaks these rules would get a new address (`/api/v2/`).

The feed gives only the order in force and the next one. The history of past orders is not published.

## What the integration does with it

- Reads this address and no other, and does not read JORAM. It has no requirements beyond Home Assistant.
- Keeps the last valid copy of the file when a fetch fails or the answer is not valid, and across restarts.
- Works out the order in force from `valid_from`, as described above, and switches at 0:00 in Madeira.
- Exposes the age of the data (`updated_at`, as the `data_updated` sensor) and the warnings (the `warnings`
  sensor: their number, with the `codes` and `messages` as attributes), so an automation can notify when the data
  is more than 8 days old or a warning is present.
- Fetches the file once an hour. It is a static file that changes about twice a week, so there is no reason to
  ask more often. The interval is fixed by the integration; there is no user setting.
