## Stage 2 Architecture

Stage 2 is divided into three layers:

1. Stage 1 jobs
   - Perform the actual Bronze, Silver, and Gold data processing.
   - Remain independent of Airflow and operational tracking.

2. Operational layer
   - Owns operational state and control logic.
   - Owns the Control Table.
   - Records completed job attempts.
   - Calculates pipeline progress.
   - Selects the next month.
   - Orchestrates pipeline execution.
   - Implements Gold batch processing.

3. Airflow
   - Owns scheduling and task execution state.
   - Calls the operational layer.
   - Handles retries and waiting.
   - Does not implement business logic such as month selection or progress calculation.


## Control Table

Its purpose is to record every completed attempt to run a Job.
One row represents one completed Job attempt.
Possible statuses: SUCCESS\FAILED

Control Table records include `layer` (`bronze`, `silver`, `gold`).
The table is written only by the operational layer.
Stage 1 jobs never write to the Control Table.

The same job, market, and load window may have multiple records because every attempt is recorded.


## Clarifications

- The Control Table records every completed attempt to run a job, including both `SUCCESS` and `FAILED` attempts. A record is written only after the attempt finishes.
- The Control Table includes `layer` (`bronze`, `silver`, `gold`) so attempts for the same logical job can be distinguished across layers.
- A month is complete only when there is a successful Bronze load, followed by a successful Silver load after that Bronze load, followed by successful Gold loads for every day of the month after that Silver load.

## Progress Calculation

Progress is computed from `control_table`; it is never stored separately.

A month is complete only when:

1. Bronze completed successfully.
2. Silver completed successfully after the relevant Bronze.
3. Every Gold day completed successfully after the relevant Silver.

A newer Bronze makes earlier Silver and Gold results stale for completion.
A newer Silver makes earlier Gold results stale for completion.

- `watermark` is the last month in the uninterrupted sequence of complete months starting at the configured earliest month.
- `complete` counts all complete months, including complete months after a gap.
- `gaps` contains incomplete months before a later complete month.
- `next` is the earliest incomplete month.
- Completed months after a gap are not reprocessed when the gap is filled.


## Pipeline

The operational pipeline supports three forms:

just run pipeline <market>
just run pipeline <market> <month>
just run pipeline <market> <month> <month>

### Gold batch retries

- Each Gold day is recorded immediately after its attempt finishes.
- Successful and failed Gold attempts are both retained.
- A failed day does not prevent the remaining days from running.
- The Gold batch fails after all days have been attempted if any day failed.
- On retry, only days without a successful attempt after the current Silver are executed.






