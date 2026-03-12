# Known Limitations

## `f1opt fantasy team` — future gameday shows no players

The F1 Fantasy API returns `null` for the `playerid` field when the requested gameday hasn't opened yet or the team hasn't been committed by the API. The balance and overall points header will display, but the player table will be empty.

**Workaround:** Use `--gameday` with the most recently completed gameday to see your active roster. Run `f1opt fantasy schedule` to identify which gameday is current.
