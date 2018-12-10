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
mix draft.github danielspofford/draft_aws_ecs \
  --app-name=your_app_name \
  --service-desired-count=2
```

- `--app-name` has only been tested to safely contain letters and numbers. It
  will be used when naming resources.
- `--service-desired-count` is the number of tasks desired to run
  simultaneously.

### Further usage

Navigate inside the created `infrastructure` folder and run `make shell`. From
within the shell you can interact with a makefile to build or destroy AWS
resources.
