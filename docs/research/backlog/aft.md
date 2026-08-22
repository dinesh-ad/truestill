# (aft) `run_health.free_bytes` RETURNS 0 WHEN IT CANNOT READ, SO AN UNREADABLE PROBE STOPS A RUN SAYING THE DISK IS FULL.

*Body of backlog entry `(aft)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aft)** Found 2026-08-22 while answering `(ady)`'s space-precondition question against
  `(aek)`. **`(aek)`'s fix reached two surfaces and not the third**, which is §4's fifty-sixth
  member: two sites agreeing is what makes the third invisible.

  ## THE CODE

  ```python
  def free_bytes(path: Path) -> int:
      """Free bytes on the filesystem holding ``path``; ``0`` when it cannot be read."""
      try:
          return shutil.disk_usage(path).free
      except OSError:
          return 0
  ```

  `run_health.py:94-99`. It feeds `RunHealth._check_space`, which compares against a floor and,
  below it, **stops the run**:

  > *"Stopped: this computer's disk is nearly full (0.0 GB free). Local free space fell by …"*

  So a probe that merely could not be read produces a **stop, with a wrong reason, naming a
  measurement nobody obtained.** The user is told to check their cloud client's cache settings
  about a disk that may be entirely empty.

  ## ⚠ THIS IS `(aek)` EXACTLY, AND `(aek)` IS ALREADY FIXED NEXT DOOR

  `filesystem.preflight_destination` carries the repair and says so in its own comment:

  > *"``None`` is 'could not measure', and it has to be distinct from a measured **0**, which is
  > what a genuinely full disk reports. `(aek)`: this was `free = 0` on failure … so the two
  > states were one value and the fallback resolved BOTH as exactly enough - a full drive passed
  > its own space check."*

  It is pinned twice - `test_a_disk_with_exactly_no_room_is_refused_rather_than_read_as_enough`
  and `test_a_destination_whose_free_space_cannot_be_read_still_proceeds`.

  ⚠ **The direction differs and that is the interesting part, not an excuse.** In
  `preflight_destination` the conflation was **silent** - a full drive passed. Here it is
  **loud and wrong** - a readable disk is declared full. `(afn)`'s cry-wolf arm is why that is not
  the safer failure: a watcher that stops good runs gets switched off, and it takes the real
  coverage with it.

  ## ⚠ THE SAME MODULE GUARDS THE OTHER AXIS AGAINST EXACTLY THIS, IN ITS OWN WORDS

  `RunHealth` watches two things. The **device** axis is careful, at `run_health.py:145-148`:

  > *"**Never let an absence serve as the baseline.** A `None` there would mean two things at once
  > - 'not yet established' and 'the device id is None' - and every later `None` reading would
  > compare equal to it, so a watcher built during one bad moment would stay silently switched off
  > for the whole run."*

  and it has five tests for transient failure - `test_one_transient_error_does_not_trip`,
  `test_two_consecutive_errors_still_do_not_trip`, `test_a_success_between_errors_resets_the_count`,
  `test_three_consecutive_errors_spanning_the_window_do_trip`,
  `test_three_errors_too_close_together_do_not_trip`.

  **The space axis has none.** Every space test uses a measured value. The author understood this
  failure precisely, wrote it down, guarded it, and applied it to one of the two axes in one class.

  ## THE OPEN QUESTION, WHICH DECIDES WHETHER THIS IS A FIX OR A DELETION

  `_check_space`'s docstring asserts a claim about the world:

  > *"One reading is enough: a local read does not fail transiently."*

  If that is **true**, the `except OSError: return 0` branch is **dead code** and should be deleted
  rather than repaired. If it is **false**, it is a live false stop. §4's thirty-first member:
  *a mutation that does not fire means either the guard is missing or the code is dead - find out
  which before writing the test.* Nobody has asked. The probe is `catalog_path.parent`, a local
  directory, which is the argument for "true"; a home directory on an autofs/NFS mount, or one
  removed mid-run, is the argument for "false".

  ⚠ **It is also a claim about a machine state in a docstring that governs behaviour**, which is
  §4's thirty-second member - the kind of sentence that expires without anyone noticing.

  ## NOT DECIDED

  - **Delete the branch, or make it `int | None`** like `preflight_destination`. The second is
    consistent and costs a signature change at three call sites; the first is smaller and rests
    entirely on the docstring's claim being verified first.
  - **What an unreadable probe should DO if the branch stays.** Not stop (that is the defect),
    and not silently continue (that is `(aek)`'s original). The device axis's answer - strikes
    before declaring anything - is right there and already tested.
  - **Whether `(ady)`'s copy should take a space precondition at all.** Verified 2026-08-22:
    neither `catalog.py` nor `catalog_startup.py` reads free space, so the copy path **inherits
    nothing** and a check there would be new code. It is deliberately absent for now - the copy
    reports its own `OSError` with the real reason, which is strictly better than a precondition
    computed from a number this entry shows can be wrong.

  ## RELATED

  `(aek)` (the same conflation, fixed in `filesystem.py`), `(ady)` (whose M6 found this),
  `(afn)` (cry-wolf: a guard that fires on ordinary input gets switched off).
