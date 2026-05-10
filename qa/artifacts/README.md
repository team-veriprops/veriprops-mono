# artifacts/

Run outputs are written here. This directory is gitignored except for this file and `.gitkeep`.

## Structure

```
artifacts/
  runs/
    <run-uuid>/
      run.ndjson          Newline-delimited JSON event stream (written live)
      report.json         Final structured run report
      <domain-name>/
        <journey-name>/
          screenshot-*.png    Full-page screenshot on step failure
          dom-*.html          DOM snapshot on step failure
          data-*.json         JSON data captured during the run
          run.log             Step-level log with timestamps
```

## Retention

Old run directories are pruned automatically at the start of each new run. The number of runs retained is controlled by `MAX_RUNS` (default: 20). Override per-invocation with `--max-runs <n>`.

## Accessing reports

```bash
# Latest run — text format
pnpm qa:report

# Latest run — HTML
pnpm qa:report --format html > report.html

# Specific run
pnpm qa:report --run-id <uuid>

# Live tail (in-progress run)
pnpm qa:report --tail
```
