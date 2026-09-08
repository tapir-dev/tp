# Transport retry is scoped to failures that have no HTTP status

The brief carries two independent retry layers and warns, in prose, that raising
the transport layer's retry count lets the HTTP client swallow rate-limit errors
before agent-level retry ever sees them. A warning is not an invariant: the knob
still exists, and the failure it describes is one config edit away. We make the
warning structural instead. **The transport may only reissue a request that
failed before any HTTP status existed** — DNS, connect, TLS handshake, a reset
before the first byte. A 429 or a 503 has a status by definition, so it can
never be visible to the transport as something reissuable, and it always reaches
the agent-level loop that emits `retry_start` / `retry_end`.

This extends a boundary the provider seam already drew. The transport never
looks inside the JSON; now it never reads a status either. What it retries is
the connection, not the request, and the config key is named for that:
`network.connect_attempts`, not a retry count.

## Considered options

- **Keep the knob at 0 and document loudly**, as the brief has it. Rejected as
  the thing the decision exists to replace: the documented footgun stays
  loaded, and the person who raises it to 3 is the person who did not read the
  paragraph.
- **Remove transport reissue entirely**, leaving one layer. Rejected because a
  connect failure is genuinely cheap to retry and genuinely uninteresting — it
  would otherwise burn an agent-level attempt and put a `retry_start` in front
  of the user for a TLS handshake that failed once.

## Consequences

The two layers stop being two policies over the same failures and become two
policies over disjoint failures, which is why they can no longer be conflated.
The cost is that a failure whose status never arrives because the connection
died mid-stream is a connect attempt on the first byte and an agent-level
attempt afterwards — the split is at the first byte, and that line has to be
implemented rather than assumed.
