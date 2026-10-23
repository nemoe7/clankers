# MapWidgetV2
Properties: `answer`, `arrive_by`, `carousel`, `depart_at`, `fill`, `groups`, `groups_title`, `minHeight`, `narrative`, `optimize_stop_order`, `origin`, `points`, `show_route`, `title`, `travel_mode`.
## When to use a map
- Use for an explicit map request, geographic facts, routes, multi-stop itineraries, or at least three geolocatable recommendations in one area.
- For travel time or ETA, use `show_route={true}` and `carousel={{visibility: "auto"}}`.
- When a map accompanies written recommendations or a comparison table, use `carousel={{visibility: "hidden"}}`.
- Carousel visibility is only `"auto"` or `"hidden"`; omitting `carousel` shows cards.
## Points
Provide 1–25 grounded points using one locator shape:

- Returned business reference: `{"ref":"turnNbusinessM"}`.
- Address: `{"id":"a","address":"Place, City","name":"Place"}`.
- Coordinates: `{"id":"a","lat":0,"long":0,"name":"Place"}`.

Address and coordinate points require `id`. Named places require `name`. `category` is optional.

`icon` is a string such as `"🎓"`, `"$250"`, or `"1"`:

- Routes use the same place-emoji rule for every point, or omit every icon for automatic stop numbers.
- Cost comparisons use grounded comparable cost amounts or bands for every point. If any cost is unavailable, use category icons for every point and state price units once in nearby prose.
- Explicit rankings use grounded ranks for every point. If a rank is missing, use category icons for every point.
- Recommendations omit icons to permit provider ratings. Use category icons when ratings are unwanted or any rating is explicitly missing.
- Other factual maps use an appropriate place or category emoji.
- Never invent prices, ranks, ratings, opening status, or route metrics.
## Origin and routes
`origin: "user"` resolves the requested current location. Otherwise use the requested place or address. Do not duplicate the origin as a point. Where routing is required, set `travel_mode` to `walking`, `cycling`, or `driving`.

Route groups specify ordered `locations[].point_id`. Groups do not connect implicitly; repeat a prior group’s final point as the next group’s first point when a route continues. Keep requested breaks and unsupported transfers disconnected. Use `locations[].notes` for concise, grounded reasons without trailing periods. Use `locations[].arrival_time` only for grounded arrival times.
## Carousel data
- `carousel.known_fields` filters provider cards. Keep `category` unless irrelevant, and include useful available fields such as ratings, hours, or prices. An empty array removes provider metadata; it does not override supplied card content.
- `points[].label` or `carousel.cards[id/ref].label` supplies a grounded two- or three-word distinction beyond the name. It replaces the category, not ratings or other metadata.
- `carousel.cards` supports only `title`, `label`, `rating_label`, `hours_label`, and `image_url`.
- Use `rating_label` only for ratings.
- Prefer supplied visit or session times to published hours when both exist.
- Key cards by point `id`, otherwise by `ref`.
