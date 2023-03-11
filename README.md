# github-to-gitlab-sync

Dockerized program to sync specific Users/Orgs

**from**: [https://Github.com](Github.com)

**to**: [https://Gitlab.com](Gitlab.com) or your self hosted Gitlab instance.

You cannot sync *specific* repos, only **all** repos under a User or Org.

----

Before you start, please read [.env.template](.env.template) to understand the env vars for this program.

Specifically note this one:

```
SYNC_MAPPING="SomeGithubOrgName:org/ThatOrgOnGitlab,torvalds:user/torvalds
```

This is the sync spec, this example would do the following:

1. Sync Github Org "SomeGithubOrgName" repos to Gitlab to a Gitlab under Group named "ThatOrgOnGitlab".
2. Sync Github User "torvalds" repos to Gitlab under Gitlab User "torvalds".

You may add as many as you wish, comma seperated.

## How to run

Create a Github Token:

https://github.com/settings/tokens/new

Create a Gitlab Token:

https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#create-a-personal-access-token

Set all the env vars within [.env.template](.env.template).

Run it:

```bash
pip install docker-compose
docker-compose build app
docker-compose run app
```

Or without docker:

```bash
pip install -r requirements.txt
bash run.sh
```
