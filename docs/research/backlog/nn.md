# (nn) Prove destination timestamp parity against a live rclone remote.

*Body of backlog entry `(nn)`, under **Records - evidence, explicitly not work**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(nn) Prove destination timestamp parity against a live rclone remote.** The destination
  timestamp seam is implemented for rclone as `touch --no-create --timestamp`. The installed
  rclone help was checked and a unit test pins the exact invocation, but **no real remote has
  exercised it**. That is command-shape evidence, not backend parity. Before claiming parity,
  run a dated normal copy against a disposable configured remote and verify its reported
  modification time equals the capture timestamp, the local source timestamps stay unchanged,
  and the failure path cannot create a zero-byte remote object.
