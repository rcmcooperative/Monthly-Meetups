# Template for setting up RCM Cooperative partner repositories
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/github/all-contributors/<github-org>/<repo-name>color=ee8449&style=flat-square)](#contributors)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

## About this Repository

This repository contains the documentation, research materials, and outputs for the <project-name> project, a collaboration between <partner-names> and [RCM Cooperative](http://rcmcooperative.com/).

This project follows open research principles to deliver FAIR and openly licensed materials. 
Publication of these materials supports transparency in this project, and reproducibility of similar work. 
All materials from the project are published as open as possible, as closed as necessary.

This repository builds on the template created and maintained by *The Turing Way* team members and shared under CC-BY 4.0 for reuse: https://github.com/alan-turing-institute/reproducible-project-template.

Note after templating this directory, you may wish to create an additional directory called `private`. 
Use this directory to enable files to be stored locally without being included in the main repo (this directory is excluded by the [.gitignore](~/.gitignore)). 
This is useful where there are restrictions on sharing some information (GDPR) or license terms are yet to be agreed. 

### Using Claude to complete this template

This repository includes a Claude Code skill, `populate-repo-template`, which helps populate the placeholder sections of this README (and related files) using project context from `CLAUDE.md`.

To use it, you'll need Claude Code set up locally.
See Anthropic's setup guide: https://docs.claude.com/en/docs/claude-code/overview

Once set up, skills live in `.claude/skills/` and are invoked automatically when relevant, or directly via `/complete-repo-template-info`.
See Anthropic's guide to skills for more: https://docs.claude.com/en/docs/claude-code/skills

For RCM Cooperative-specific guidance on working with Claude (including this skill), see <mark>link to our "how we use AI" repo, once created</mark>.

## Vision and Mission
<See materials from [Community Pulse](https://www.communitypulse.io/50-metrics-kpis-and-okrs/) for more guidance on developing the vision and mission.>

- **Vision:** <A short phrase describing the future you are ultimately working towards (your final destination or desired end state).>
- **Mission:** <A one-sentence statement describing the reason your organization or program exists (what you do + who/what you do this for).>

## About

<Motivation and background in a nutshell.>

## Roadmap & Milestones

- **Goals:** <Clear overview of overarching and short-term goals.>
- **Outcomes:** <Description of expected results and deliverables.>

## The Team

- **Members:** <List of team members and their roles in the project.>
- **Roles & Responsibilities:** <Outlines roles, responsibilities and their ways of working.>

## Contributing

- **Guidelines:** [Contribution Guidelines](CONTRIBUTING.md) for contributors.
- **Code of Conduct:** [Code of Conduct](CODE_OF_CONDUCT.md) ensures a respectful project environment.

## Licensing

This project is licensed under the CC-BY-4.0 License for documentation and an MIT license for any code - see the LICENSE.md file for details.

## Citing & Acknowledgement

- **Citation Instructions:** <How to cite the project.>
- **Acknowledgement:** <Recognising contributions by different members.>

## Contact

- **Reach Out:** <Contact details for questions, feedback, or ideas.>

## Contributors

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->


<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!


## Checklist for setting an online repository 

This repo has been templated from the [RCM Cooperative Partner template repo](https://github.com/rcmcooperative/partner-template), including file structure, starter contents and a Claude Skill to fill in template information. 

After running the Claude skill, please review the list below to and check off once completed.

This repo includes:

- [ ] A meaningful and accurate README.md
- [ ] A meaningful and accurate [CONTRIBUTING](CONTRIBUTING.md) file
- [ ] A [LICENSE](LICENSE.md) (we suggest MIT for code and CC-BY-4.0 for documentation)
- [ ] A [Code of Conduct](CODE_OF_CONDUCT.md) (we suggest RCM Cooperative CoC)
- [ ] A directory for project management (communications, meetings, reports, proposals)
- [ ] A directory for assets (non-code supporting files such as images, diagrams, templates, and similar media) that are used in the projects documentation or output)
- [ ] A directory for documentation
- [ ] Directories for any research materials if appropriate for the project (ethics, data, analysis)
- [ ] Ready to use [all-contributors](https://allcontributors.org/) bot (installed for the RCM Cooperative GitHub organisation)
- [ ] Appropriate issue templates
- [ ] Appropriate .gitignore file
- [ ] Connect repo with Zenodo <mark>the order of these needs to be reviewed</mark>
- [ ] Add cff file for citation (we suggest creating this with https://bit.ly/cffinit)
- [ ] Add a DOI badge (see the zenodo doi badge widget)
