# Upstream and personal extension

This repository is derived from the MIT-licensed
[EcomAgent](https://github.com/yoligehude14753/ecom-agent) project.

The original EcomAgent architecture, backend modules, frontend, documentation,
and test suite remain attributed to the upstream contributors. The MIT license
in [LICENSE](LICENSE) is preserved.

Personal extension scope:

- CSV batch input parsing with Excel-friendly UTF-8 BOM support
- bounded-concurrency listing generation with row-level error isolation
- Amazon-facing output validation and human-review status
- Excel-friendly CSV export with formula-injection protection
- CLI workflow, Chinese operating guide, sample data, and focused tests

This attribution file records the boundary between upstream work and the
personal extension so the project history is not misrepresented.
