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
mix draft.execute danielspofford/draft_aws_ecs namespace
```

`namespace` can be any string, usually a project name. It will be used when
naming resources.

### Further usage

Navigate inside the created `infrastructure` folder and run `make shell`. From
within the shell you can interact with a makefile to build or destroy AWS
resources.
