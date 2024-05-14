# Benchmark Runner

benchmark.sh is expected to be run a cronjob (once a week or fortnightly?) to run synthetic benchmarks on different "standard" shaped vms.
The pre-requisite to running the benchmark is to create a "perfkit.results" (dataset.table) in BQ. Result of all successful runs is exported into this table.
From sa-tools, the synthetic benchmark section under Periscope will fetch results from the cron runs.

To customize the tests, the corresponding yaml files need to be modified. These config files (and the corresponding execution script) is available in custom_benchmarks directory.
The standalone Perfkit Benchmarker utility in sa-tools will load config files from this directory. The user will either accept defaults or make changes, and run the test.
On successful completion, the results are exported to perfkit.results in BQ. From the sa-tools UI, the results are fetched from this table.

Since both cronjob and custom runs store the results in the same table, the results (for Periscope flow vs standalone Perfkit) are differentiated based on the metadata.
For custom test runs, the results metadata consists of the job-id of the run, whereas cronjobs have no such associated ids.
