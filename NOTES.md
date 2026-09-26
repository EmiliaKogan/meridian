# Development Notes

## Stage 2

### Control Table

`operational_loads` is a successful-load ledger.

A record is written only after the corresponding Stage 1
job has completed successfully.

Airflow owns execution state such as:
- success
- failure
- retries
- upstream failures

Stage 1 jobs never write to `operational_loads`.

### Progress

Operational progress is calculated from `operational_loads`
when requested. It is not stored separately.

A month is complete when:
1. its Silver load was recorded, and
2. all Gold day loads were recorded after that Silver load.

### Month Selection

Month selection was initially implemented as a separate
`month_selection.py` module.

It only returned:

    progress(conn, job)["next"]

Since it added no independent behavior, the module was removed.
The pipeline uses the `next` value from `progress()` directly.

### Configuration

Market/job mappings and earliest supported months are kept
in the operational configuration module.