# cdk-starter

If you're interested in creating  Infrastructure as Code (IaC) projects in AWS,
you've come to the right place. This project is my starting point and I'm happy
to talk about it. 

If you are using this as a GitHub template repository, start with
[CUSTOMIZE.md](./CUSTOMIZE.md).

## Quick Start (Template Consumers)

```console
make .venv
make node_modules
make unit-test
```

If naming changes cause golden-file diffs, run:

```console
make unit-update_golden
make unit-test
```

This project is part pitch and part demonstration. 

There are 4 main reasons to choose CDK in AWS:
1) Free and full support from the cloud provider. AWS will help you with CDK
problems.
2) Delegate state management to AWS Cloudformation. Only deal with templates
and leave the state management and synchronization to battle-tested
cloudformation. By contrast, some other tools will force you to protect and
upgrade your own state data across breaking changes.
3) I can't stress this next one enough: Test hooks make it trivially easy to
test for unintentional template changes. I'm familiar with pytest in python, so
I use that. But CDK supports several languanges and their test hooks. Pick your
favorite and go to town.
4) Programming language support: Having chosen your favorite language for CDK,
you can then extend yor CDK project with the same. In this project, CDK builds
my resources, and I extend that with pyton modules that do things like discover
AMI IDs, external peering targets, etc.
5) Automatic resource tagging: CDK makes it easy to automatically tag all taggable resources. This is important if you have many teams sharing a sandbox account. They make it easy to clean up.

I like tags like:

 - 'owner' ('Nate Marks')
 - 'owner_email' ('npmarks@gmail.com')
 - 'iac_project' ('github.com/natemarks/cdk-starter')



NOTE: GNU Make is useful for automating common project tasks, like testing and
static checks. I also use it to simplify pipeline execution of CDK commands. It
keeps the pipelines clean, and I can test the automation locally.

I enjoy this stuff, so if you have questions, I'll try to help.  Drop me an
email, but be prepared to wait. :)

## Demonstration

CDK deploys and destroys Cloudformation stacks. This project demonstrates
infrastructure deployment patterns using Python and CDK.

app_vpc.py deploys a VPC with a few of my favorite features. This is a unique
stack, meaning that there will be exactly one app vpc stack in each
environment.

### CDK Usage

Using 'make cdk-ls' and providing the target environment, cdk prints the stacks
that exist for the dev environment. 
```console
foo@bar:~$ make cdk-ls app_env=dev
   ...
StarterDevAppVpcStack
```

I can use the make target 'cdk-diff' and 'cdk-diff-all' to see if the project
template would change the AWS deployed stack.

If I run the 'cdk-diff-all' target, it diffs every stack in the environment

```console
foo@bar:~$ make cdk-diff app_env=dev stack=StarterDevAppVpcStack
 ...
start: Building 69f29bc9ba86d9acc02d6e91ebe003b265184e8bd7238569531453e75854fbaa:709310380790-us-east-1
success: Built 69f29bc9ba86d9acc02d6e91ebe003b265184e8bd7238569531453e75854fbaa:709310380790-us-east-1
start: Publishing 69f29bc9ba86d9acc02d6e91ebe003b265184e8bd7238569531453e75854fbaa:709310380790-us-east-1
success: Published 69f29bc9ba86d9acc02d6e91ebe003b265184e8bd7238569531453e75854fbaa:709310380790-us-east-1
Hold on while we create a read-only change set to get a diff with accurate replacement information (use --no-change-set to use a less accurate but faster template-only diff)
Stack StarterDevAppVpcStack
There were no differences

✨  Number of stacks with differences: 0
```


'cdk-deploy' and 'cdk-deploy-all' work the same way as 'cdk-diff' and
'cdk-diff-all' above. The deploy commands create or update the specified stacks
deployed in AWS.


I have a 'cdk-destroy' target that works like 'cdk-diff' and 'cdk-deploy'. You
must specify the target stack.  I don't have a 'cdk-destroy-all' because I'm a
coward.

### Pytest Golden Files

CDK test hooks allow me to easily compare a stack template to the expected
template in my pytests. It's a great way to know when a change to the project
unintentially changes a template. To accomplish this, every stack test case has
a golden file. Theses stack test are marked as unit tests. Running 'make
unit-test' will run all such tests. If the project has changed and the actual
template no longer matches the expected template, the test will fail. If the
change is intended, run 'make unit-update-golden'. All the unit test golden
files will be updated. Use git to view and keep/reset the changes.


### Discovery

The environment-specific config files are maintained in the project repo:

 - config/dev/
 - config/staging/
 - config/production/

The data is often generated manually and is fairly static.  However, sometimes I
need to store data from external sources and it's safer and easier to automate
the process of updating parts of the configuration data.

The discovery process can be extended to automate configuration data updates.
Run discovery manually and commit the changes to the repo, or run it in your
pipeline before CDK commands to always use the latest discovered data.



## Polls

Simple public polls served at `polls.natenite.net/<poll-id>`. A respondent
answers a poll's questions and may leave an email address; only the owner
reads the data. Terms are defined in [CONTEXT.md](./CONTEXT.md), the reasons
for the hosting choice are in
[ADR 0001](./docs/adr/0001-lambda-function-url-with-cloudfront-oac.md), and
the full requirements are in the
[spec](./.scratch/wayfinder/poll-app/spec.md).

### Add a poll

1. **Write the definition** as `polls/<poll-id>.json`. The file name must
   match the `id`. `docs/examples/all-question-types.json` shows every
   question type (it is not published; only `polls/` is).
2. **Run the unit tests** with `make unit-test`. They check every file in
   `polls/`, so a mistake (a duplicate option, a rating range that is too
   wide, a poll too big to submit) fails here, before anything is deployed.
3. **Preview** the change with `make diff-polls`. Adding a poll should change
   the poll files (the definitions upload and the function bundle).
4. **Deploy** with `make deploy-polls`. It runs the unit tests first.
5. **Check the live page.** Open `https://polls.natenite.net/<poll-id>`,
   answer it, then run `make dump-poll poll=<poll-id>` to see the stored
   response. Test responses stay in the table, so expect to see your own.

To change a poll that is already open, edit its file and raise `version`
(each stored response records the version it answered). To stop taking
responses, add `closesAt`; to unpublish a poll, delete its file and deploy.

### Poll definition format

```json
{
  "id": "poll-id",
  "title": "Shown at the top of the page",
  "version": 1,
  "closesAt": "2026-12-31T23:59:59Z",
  "questions": [ ... ]
}
```

| Field | Rule |
| --- | --- |
| `id` | Lower-case letters, digits and hyphens; equals the file name. |
| `title` | Non-empty text. |
| `version` | Whole number, at least 1. |
| `closesAt` | Optional, UTC, exactly as above. After it the page says the poll is closed and submissions are refused. |
| `questions` | A non-empty list. Each has a `prompt`, a `type`, and an `id` that starts with a lower-case letter and uses letters, digits and underscores. |

Question types:

- `single` and `multi`: `options`, at least two, each with an `id` and a
  `label`. A `multi` answer is a list of option IDs.
- `rating`: whole-number `min` and `max`, at most 10 steps apart.
- `text`: free text, up to 500 characters.

A submission body may not exceed 6 KB, so a poll can hold at most two
free-text questions. The email address, if given, is stored as a separate
record and is never included in `make dump-poll`.

### Checking on it

These are all run by the owner; nothing here is automatic.

- `make dump-poll poll=<poll-id>`: the stored responses, as JSON.
- `make query-logs [days=90]`: the routine CloudFront log queries (errors by
  day, busiest client addresses, requests blocked or throttled) as one JSON
  document, for reading or for automation. The same three queries are saved
  in the Athena workgroup `NateNiteProductionPolls-access-logs`.
- Four saved CloudWatch Logs Insights queries (rejections by reason, errors,
  submissions per day, recent requests) search the submit function's log.
- `make purge-emails days=365` and `make delete-email email=<address>` report
  what they would remove; add `yes=1` to do it.

Submissions are limited to about 20 per five minutes from one address; the
limit is an estimate by the web firewall, not an exact count. The function's
logs and the access logs are each kept for a year.

## Contributing

If you'd like to contribute to this project read
[CONTRIBUTING.md](CONTRIBUTING.md).
