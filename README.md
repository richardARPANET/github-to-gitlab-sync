# github-to-gitlab-sync

Dockerized program to sync a list of repos from Github to Gitlab

Create a Github Token:

https://github.com/settings/tokens/new

Create a Gitlab Token:

https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#create-a-personal-access-token

How to run

1. Set all the env vars within `.env.template`.

2. Run it

```bash
pip install docker-compose
docker-compose run app
```

Or without docker:

```bash
bash run.sh
```
