# Endpoint evidence and coverage

Base: `https://us.edstem.org/api`. Every API call uses GET and bearer authentication.
All path placeholders are strictly positive numeric IDs. No operation accepts arbitrary
methods, URLs, paths, or query parameters. `view` is never accepted or sent.

Sources reviewed on 2026-09-23:

- Ed's token help supplied by the owner documents `/user` and bearer authentication.
- [Ed's current web client](https://edcdn.net/js/7d7cda8f.js), linked from
  [the US app](https://edstem.org/us/): DiscussApi, ProfileApi, LessonApi, ResourceApi,
  SnippetApi, and lab methods. The thread, lesson, and slide getters make view tracking
  explicitly opt-in. We omit that option. Native search uses its own `/threads/search` route.
- [edpy client](https://github.com/bachtran02/edpy/blob/79f1502da8d82dc0238a0469153a5cd6b92b2839/edpy/client.py)
  and [transport](https://github.com/bachtran02/edpy/blob/79f1502da8d82dc0238a0469153a5cd6b92b2839/edpy/transport.py).
  Its WebSocket subscription is intentionally excluded.
- [edapi implementation](https://github.com/smartspot2/edapi/blob/9199e1001eb04b86bb8f68d0c5f9042453cd1387/edapi/edapi.py)
  and [endpoint notes](https://github.com/smartspot2/edapi/blob/9199e1001eb04b86bb8f68d0c5f9042453cd1387/docs/api_docs.md).
- [ed-mcp client](https://github.com/januarharianto/ed-mcp/blob/main/src/edstem_mcp/client.py)
  for attendance and analytics reads. Its `filter=search:...` approach was tested and found
  ineffective; we do not use it.
- [edstem-cli client](https://github.com/bunizao/edstem-cli/blob/main/src/ed/client.ts)
  for lesson questions and existing response reads.
- [campus-copilot resource notes](https://github.com/xiaojiou176-open/campus-copilot/blob/main/docs/site-capability-matrix.md),
  subsequently corroborated by Ed's own ResourceApi and live results.

## Catalog

`200` means a live request succeeded with this account. It does not guarantee every resource
is accessible or that an empty list contains hidden/unreleased data. `Source only` means the
read was reviewed in client source but no suitable live record was available.

| Operation | Path | Evidence/result |
| --- | --- | --- |
| user | `/user` | Official help; 200, six courses |
| course | `/courses/{course_id}` | ed-mcp; 200 |
| threads | `/courses/{course_id}/threads` | Ed DiscussApi; 200 in six courses |
| native_search | `/courses/{course_id}/threads/search` | Ed DiscussApi; positive and no-match tests pass |
| thread | `/threads/{thread_id}` | Ed DiscussApi/edpy; 200, replies confirmed |
| course_thread | `/courses/{course_id}/threads/{number}` | Ed DiscussApi/edapi; 200 |
| user_activity | `/users/{user_id}/profile/activity` | Ed ProfileApi/edapi; 200 |
| user_stats | `/users/{user_id}/profile/stats` | Ed ProfileApi; 200 |
| resources | `/courses/{course_id}/resources` | Ed ResourceApi; 200, entries in one course |
| user_resources | `/users/resources` | Ed ResourceApi; 200 |
| lessons | `/courses/{course_id}/lessons` | Ed LessonApi; 200, empty in six courses |
| user_lessons | `/users/lessons` | Ed LessonApi; 200 |
| lesson | `/lessons/{lesson_id}` | Ed LessonApi, source only; omit view/password |
| slide | `/lessons/slides/{slide_id}` | Ed LessonApi, source only; omit view/password |
| slide_questions | `/lessons/slides/{slide_id}/questions` | edstem-cli, source only |
| slide_responses | `/lessons/slides/{slide_id}/questions/responses` | edstem-cli, source only |
| snippets | `/courses/{course_id}/snippets` | Ed SnippetApi; 200; no execution |
| labs | `/courses/{course_id}/labs` | Ed lab methods; 200 |
| lab_categories | `/courses/{course_id}/lab_categories` | Ed lab methods; 200 |
| events | `/courses/{course_id}/events` | ed-mcp; 200, empty sample |
| event | `/events/{event_id}` | ed-mcp, source only |
| check_ins | `/courses/{course_id}/check_ins` | ed-mcp; 200, empty sample |
| event_check_ins | `/events/{event_id}/check_ins` | ed-mcp, source only |
| course_stats | `/courses/{course_id}/stats` | ed-mcp; 403 in sampled course |
| enrollment_stats | `/courses/{course_id}/analytics/enrollments` | ed-mcp; 403 in sampled course |
| course_users | `/courses/{course_id}/analytics/users` | edapi; 403 in sampled course |
| attendance_stats | `/courses/{course_id}/analytics/sessions` | ed-mcp; 403 in sampled course |

The catalog in `src/edstem_mcp/catalog.py` is authoritative for query fields and bounds.
Thread lists/search and activity use bounded limit/offset pagination. A full page produces
`next_query`; an extra empty page may be needed. Concurrent course activity can shift offsets.
Other reads expose the returned JSON without claiming there are no hidden records.

Native search uses `query`, optional category/subcategory/subsubcategory, and limit/offset.
Ed controls its indexing and reply coverage. The local search tool can explicitly inspect
reply text, match all keywords, and filter exact category or post type, with resumable offsets.

## Files and unsupported areas

Embedded attachment URLs must originate in an accessible thread/resource/lesson/slide response
and match the fixed US Ed CDN host and file-path rules. Tokens never go to the CDN. PDF text
and PNG image reads were verified live. Resource records without direct CDN links remain
available as metadata: the dedicated `/resources/{id}/download` route returned 404 with this
token, both with and without a filename, and is not exposed by this MCP.

There are no chat/notification reads, WebSockets, bulk export POSTs, API token management,
user administration, external website fetches, workspace launches, code execution, submission
or assessment-start routes. These omissions prevent known or insufficiently understood writes.
The integration is broad, but is not a complete implementation of Ed's website or private API.

## Change feed, October 30, 2026

No upstream route was added. The feed reuses `user`, `threads` and `thread` from
this reviewed catalog. It follows every bounded list page and reads full threads,
including nested answers/comments on older threads. It never sends `view` or read flags,
opens WebSockets, acknowledges notifications, or invokes a mutation. See change-feed.md.

The `changes` operation is local snapshot reconciliation exposed through the existing read
wrapper; it is deliberately absent from the HTTP route catalog. Its arguments are validated
before authorization and campus reads. It delegates only to the same reviewed adapters as
the dedicated feed tool, adding no upstream routes or methods. See `docs/change-feed.md`.
