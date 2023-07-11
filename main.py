import os
from pathlib import Path
import shutil
import time

from git import Repo
from git.exc import GitCommandError
from github import Github
import github
import gitlab
import gitlab.client
from gitlab.client import Optional, Dict, Any, List

SECS_SLEEP_BETWEEN_RUNS = int(os.environ['SECS_SLEEP_BETWEEN_RUNS'])
RUN_CONTINUOUSLY = (
    os.environ.get('RUN_CONTINUOUSLY', 'false').lower() == 'true'
)
try:
    GITLAB_URL = os.environ['GITLAB_URL'].rstrip('/')
except KeyError:
    GITLAB_URL = 'https://gitlab.com'
GITLAB_USERNAME = os.environ['GITLAB_USERNAME']
GITLAB_PASSWORD = os.environ['GITLAB_PASSWORD']
GITLAB_URL_AUTHD = GITLAB_URL.replace(
    'https://', f'https://{GITLAB_USERNAME}:{GITLAB_PASSWORD}@'
)
GITLAB_API_PRIVATE_TOKEN = os.environ['GITLAB_API_PRIVATE_TOKEN']
GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
SYNC_CONFIG = os.environ['SYNC_CONFIG']
github_ = Github(os.environ['GITHUB_TOKEN'])


def get_sync_mapping():
    mapping = {}
    for item in SYNC_CONFIG.split(','):
        source_user_or_org, dest = item.split(':')
        type_, dest_user_or_org = dest.split('/')
        mapping[source_user_or_org] = {
            'name': dest_user_or_org,
            'type': type_,
        }
    return mapping


class CustomGitlabList(gitlab.client.GitlabList):
    def _query(
        self,
        url: str,
        query_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        query_data = query_data or {}
        result = self._gl.http_request(
            'get', url, query_data=query_data, **kwargs
        )
        try:
            next_url = result.links['next']['url']
        except KeyError:
            next_url = None

        if next_url:
            next_url = next_url.replace(':80', '')

        self._next_url = self._gl._check_url(next_url)
        self._current_page: Optional[str] = result.headers.get('X-Page')
        self._prev_page: Optional[str] = result.headers.get('X-Prev-Page')
        self._next_page: Optional[str] = result.headers.get('X-Next-Page')
        self._per_page: Optional[str] = result.headers.get('X-Per-Page')
        self._total_pages: Optional[str] = result.headers.get('X-Total-Pages')
        self._total: Optional[str] = result.headers.get('X-Total')

        try:
            self._data: List[Dict[str, Any]] = result.json()
        except Exception as e:
            raise gitlab.exceptions.GitlabParsingError(
                error_message='Failed to parse the server message'
            ) from e

        self._current = 0


gitlab.GitlabList = CustomGitlabList
gitlab.client.GitlabList = CustomGitlabList


def main():
    print('Starting')
    for item in get_sync_mapping():
        print(f'Processing {item}')
        _process_org_or_user(item)
    print('Done')


def _process_org_or_user(org_or_user_name):
    try:
        org_or_user = github_.get_organization(org_or_user_name)
    except Exception:
        org_or_user = github_.get_user(org_or_user_name)
    for repo in org_or_user.get_repos():
        names = [repo.owner.login]
        try:
            names.append(repo.organization.url.split('/')[-1])
        except AttributeError:
            pass
        except github.GithubException as exc:
            print(exc)
            continue

        _push_repo_to_gitlab(repo=repo)


def _gitlab_client():
    return gitlab.Gitlab(
        url=GITLAB_URL,
        private_token=GITLAB_API_PRIVATE_TOKEN,
        api_version=4,
        http_username=GITLAB_USERNAME,
        http_password=GITLAB_PASSWORD,
    )


def _repo_exits_on_gitlab(*, repo_owner_name, repo_name):
    group_exists, user_exists, repo_exists, repo_is_public = (
        False,
        False,
        False,
        False,
    )
    gl = _gitlab_client()
    try:
        user = gl.users.list(username=repo_owner_name)[0]
    except IndexError:
        group = [
            g
            for g in gl.groups.list(get_all=True)
            if g.name == repo_owner_name or g.path == repo_owner_name
        ][0]
        projects = [p for p in group.projects.list(owned=True, get_all=True)]
        group_exists = True
    else:
        user_exists = True
        projects = [p for p in user.projects.list(owned=True, get_all=True)]

    try:
        project = [p for p in projects if p.path == repo_name][0]
    except IndexError:
        repo_exists = False
    else:
        repo_exists = True
        repo_is_public = project.visibility == 'public'

    return group_exists, user_exists, repo_exists, repo_is_public


def _push_repo_to_gitlab(repo):
    org_name = None
    owner_name = None
    try:
        org_name = repo.organization.url.split('/')[-1]
    except AttributeError:
        owner_name = repo.owner.login

    repo_owner_name = get_sync_mapping()[org_name or owner_name]['name']
    owner_type = get_sync_mapping()[org_name or owner_name]['type']

    (
        group_exists,
        user_exists,
        repo_exists,
        repo_is_public,
    ) = _repo_exits_on_gitlab(
        repo_owner_name=repo_owner_name, repo_name=repo.name
    )
    if (group_exists or user_exists) and not repo_exists:
        if owner_type == 'user':
            _create_gitlab_repo(
                user_name=repo_owner_name,
                repo_name=repo.name,
                repo_is_public=repo_is_public,
            )
            _push_all_branches_to_gitlab(
                source_owner_name=org_name or owner_name,
                user_name=repo_owner_name,
                repo_name=repo.name,
            )
        else:
            _create_gitlab_repo(
                group_name=repo_owner_name,
                repo_name=repo.name,
                repo_is_public=repo_is_public,
            )
    elif (group_exists or user_exists) and repo_exists:
        _push_all_branches_to_gitlab(
            source_owner_name=org_name or owner_name,
            group_name=repo_owner_name,
            repo_name=repo.name,
        )


def _create_gitlab_repo(
    *, repo_name, repo_is_public, user_name=None, group_name=None
):
    gl = _gitlab_client()
    visibility = 'public' if repo_is_public else 'private'
    if group_name:
        namespace_id = [
            n.id
            for n in gl.namespaces.list()
            if n.name == group_name or n.path == group_name
        ][0]
        gl.auth()
        user = gl.users.list(username=gl.user.username)[0]
        project = user.projects.create(
            {
                'name': repo_name,
                'visibility': visibility,
                'namespace_id': namespace_id,
            }
        )
    else:
        user = gl.users.list(username=user_name)[0]
        project = user.projects.create(
            {'name': repo_name, 'visibility': visibility}
        )
    return project


def _push_all_branches_to_gitlab(
    *, source_owner_name, repo_name, user_name=None, group_name=None
):
    clone_url = f'git@github.com:{source_owner_name}/{repo_name}.git'
    checkout_branches = [
        'master',
        'main',
        'trunk',
        'ci-cd',
        'develop',
        'radius',
    ]
    print('Cloning', clone_url)
    path = Path(f'/tmp/git/{repo_name}')

    source_repo = None
    for branch in checkout_branches:
        try:
            shutil.rmtree(str(path), ignore_errors=True)
            source_repo = Repo.clone_from(
                clone_url,
                path,
                branch=branch,
                env={
                    'GIT_SSH_COMMAND': (
                        'ssh -o StrictHostKeyChecking=no -i /root/.ssh/id_rsa'
                    )
                },
            )
        except GitCommandError as exc:
            print(exc)
            continue
        except IndexError as exc:
            print(exc)
            return None
        if source_repo:
            break

    if not source_repo:
        print(f'Failed to clone: {clone_url}')
        return None

    refs = []
    for origin in source_repo.remotes:
        origin.fetch()
        origin.pull()
        refs.extend(origin.refs)

    dest_url = f'{GITLAB_URL_AUTHD}/{user_name or group_name}/{repo_name}.git'
    destination_origin = source_repo.create_remote('dest', dest_url)

    for refspec in refs:
        if refspec.name.endswith('/HEAD'):
            continue
        refspec.checkout()
        branch = '/'.join(refspec.name.split('/')[1:])
        try:
            source_repo.git.checkout(b=branch)
        except GitCommandError:
            source_repo.git.checkout(branch)
        print(f'Pushing {branch} of {clone_url} to {destination_origin.url}')
        try:
            destination_origin.push(force=True).raise_if_error()
        except GitCommandError as exc:
            print(exc)
            print(f'Failed to push {branch} of {clone_url}')
    shutil.rmtree(str(path), ignore_errors=True)


if __name__ == '__main__':
    if RUN_CONTINUOUSLY is True:
        print('Running continuously')
        while True:
            main()
            print(f'Sleeping for {SECS_SLEEP_BETWEEN_RUNS} seconds...')
            time.sleep(SECS_SLEEP_BETWEEN_RUNS)
    else:
        main()
