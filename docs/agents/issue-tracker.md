# Issue tracker: GitHub

Issues and PRDs for this repo live as GitHub issues in `sott1301/SunTerra-LEG-Portal`.

Use the `gh` CLI for issue operations. Until the local working directory is initialized as a clone with a GitHub remote, pass the repository explicitly with `-R sott1301/SunTerra-LEG-Portal`.

## Conventions

- **Create an issue**: `gh issue create -R sott1301/SunTerra-LEG-Portal --title "..." --body "..."`. Use a heredoc or body file for multi-line bodies.
- **Read an issue**: `gh issue view -R sott1301/SunTerra-LEG-Portal <number> --comments`, including labels.
- **List issues**: `gh issue list -R sott1301/SunTerra-LEG-Portal --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment -R sott1301/SunTerra-LEG-Portal <number> --body "..."`
- **Apply / remove labels**: `gh issue edit -R sott1301/SunTerra-LEG-Portal <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close -R sott1301/SunTerra-LEG-Portal <number> --comment "..."`

When the working directory becomes a normal clone of this GitHub repo, `gh` can infer the repository from `git remote -v`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue in `sott1301/SunTerra-LEG-Portal`.

## When a skill says "fetch the relevant ticket"

Run `gh issue view -R sott1301/SunTerra-LEG-Portal <number> --comments`.
