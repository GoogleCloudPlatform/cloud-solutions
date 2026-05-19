# Google Cloud solutions

[![Docs](https://img.shields.io/badge/docs-live-4285F4)](https://googlecloudplatform.github.io/cloud-solutions/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Open source reference implementations from the Google Cloud Solutions Architects team. The repository combines multiple Google Cloud services into practical blueprints, demos, and reusable building blocks for common platform, data, AI, and security workflows.

## Table of contents
- [What is in this repository](#what-is-in-this-repository)
- [How to explore the projects](#how-to-explore-the-projects)
- [Repository layout](#repository-layout)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Support notice](#support-notice)
- [License](#license)

## What is in this repository
This repo is a source companion for the Cloud Solutions docs site. It is useful when you want to:

- browse end-to-end examples before starting a new Google Cloud build
- study production-oriented reference architectures from Solutions Architects
- reuse implementation patterns across AI, data, security, and modernization projects
- contribute fixes or new solution templates back to the catalog

## How to explore the projects
1. Start with the published docs site: <https://googlecloudplatform.github.io/cloud-solutions/>.
2. Open the `projects/` directory to find solution source code grouped by topic.
3. Use `docs/index.md` and `docs/mkdocs.yaml` to understand how solution docs are organized.
4. Follow each project folder's local README or docs for service-specific setup and deployment steps.

## Repository layout
- `projects/` , solution source code and example implementations
- `docs/` , MkDocs content for the public documentation site
- `config/lint/` , shared linting and repository quality rules
- `.github/workflows/` , CI and site deployment automation

## Documentation
- Docs site: <https://googlecloudplatform.github.io/cloud-solutions/>
- Solutions Center: <https://solutions.cloud.google.com/>
- Google Cloud Architecture Center: <https://cloud.google.com/architecture>
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)

## Contributing
Contributions are welcome. If you want to propose a new solution or improve an existing one, please start with [CONTRIBUTING.md](CONTRIBUTING.md) and check the relevant project folder for local conventions.

## Support notice
Projects in this repository are not officially supported Google products and are not eligible for the [Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).

## License
All files in this repository are licensed under the [Apache License 2.0](LICENSE), unless noted otherwise.
