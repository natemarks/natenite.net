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



## Contributing

If you'd like to contribute to this project read
[CONTRIBUTING.md](CONTRIBUTING.md).
