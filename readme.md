# Draft AWS ECS

A [Draft](https://github.com/danielspofford/draft) template for standing up a
web stack on AWS with ECS and RDS via
[Stacker](https://github.com/cloudtools/stacker).

## Usage

### Template execution

Install the `draft` mix archive if you haven't already:

```
mix archive.install github danielspofford/draft
```

Execute this template:

```
mix draft.github danielspofford/draft_aws_ecs --app-name=your_app_name
```

`--app-name` must be a string and has only been tested to safely contain
letters, numbers, and hyphens. It will be used when naming resources.

### Further usage

Navigate inside the created `infrastructure` folder and run `make shell`. From
within the shell you can interact with a makefile to build or destroy AWS
resources.
