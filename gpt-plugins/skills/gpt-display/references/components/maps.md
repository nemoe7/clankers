# GPT Display: MapWidgetV2 properties and schemas

Read this file before writing a `<MapWidgetV2>` block. The decision rules for choosing
a map live in SKILL.md section 9.

## Main properties

`answer`, `arrive_by`, `carousel`, `depart_at`, `fill`, `groups`, `groups_title`, `minHeight`, `narrative`, `optimize_stop_order`, `origin`, `points`, `show_route`, `title`, `travel_mode`.

## Points schema

The `points` array contains 1–25 grounded locations. Each point must use a supported locator:

- Business: `{"ref":"turnNbusinessM"}` using the exact business ref.
- Address: `{"id":"a","address":"Place, City","name":"Place"}`.
- Coordinates: `{"id":"a","lat":0,"long":0,"name":"Place"}`.

The IDs and values above are examples, not factual locations. Address and coordinate points require an `id` and a `name`. Do not use search or news references as business locators.

Optional fields include `category` and `icon`. Ground all locations and details in source evidence. Do not invent hours, ratings, costs, addresses, coordinates, travel times, or availability.

## Groups and routes

`groups` may contain `title`, `travel_mode`, and `locations`: ordered objects with `point_id`, and optional `notes` or `arrival_time`.

Routed groups do not connect automatically. Repeat the prior group's final point as the next group's first point when the route must remain continuous. Leave requested breaks or unsupported transfers unconnected.

For routes or travel-time tasks, use `show_route={true}` and `carousel={{visibility: "auto"}}`. Do not invent route metrics. Use `origin="user"` only when current location is the intended origin. Do not repeat the origin as a point.

For a pin-only map, omit route-only properties. Use `carousel={{visibility: "hidden"}}` when written cards or a comparison table already give the needed place details.

## Carousel schema

`carousel` supports `visibility` (`"auto"` or `"hidden"`), `known_fields`, and `cards`.

- `known_fields` filters provider metadata such as category, rating, hours, and price. An empty array removes provider metadata but does not override it.
- `cards` uses a point ID or ref as its key. Each card accepts `title`, `label`, `rating_label`, `hours_label`, and `image_url`.
- Use `rating_label` only for ratings.
- Use supplied session or visit times before published hours when both apply.
- Do not infer current availability from published opening hours.

## Map icon rules

- For routes, use a place emoji for every point or omit icons for all points. Omitted route icons can indicate stop numbers.
- For cost comparisons, use comparable costs for every point. If one cost is missing, use category icons for every point and state prices in prose.
- For explicit rankings, use sourced ranks for every point or category icons for all points.
- For business recommendations, omit icons by default to allow provider ratings. If ratings are unwanted or missing, use category icons for all points.
- For other factual maps, use relevant place or category icons.
- Keep `points[].icon` to eight characters or fewer. State price units once in nearby prose.
