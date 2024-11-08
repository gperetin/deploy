# Deploy simple Python services

This is a tool I use to deploy simple Python services. It uses SSH to copy files from a local directory to a remote host, install dependencies using `uv` and starts a service defined in a systemd unit file. The entire tool is contained in the `deploy.py` file, the rest is for testing.

## Requirements

- Remote host has `uv` installed and uses systemd
- Service being deployed is managed (supervised) by systemd as a user service

## Usage

This tool uses [Inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/#inline-script-metadata) to declare its dependencies, so it can be ran using `uv` without installing any dependencies.

    uv run deploy.py

Or, without checking out the repo:

    curl -LsSf https://raw.githubusercontent.com/gperetin/deploy/refs/heads/main/deploy.py | uv run -

## Configuration

There are 3 required parameters:

- `host`: Server where the service is being deployed to, supports SSH style syntax, eg. `user@host`, or anything that can be passed into [Fabric's Connection](https://docs.fabfile.org/en/latest/api/connection.html#fabric.connection.Connection.__init__)
- `dir`: *Absolute* path to the directory where the app should be deployed. **THIS DIRECTORY IS REMOVED ON EACH DEPLOY**.
- `app_name`: Name of the service being deployed. The final path to the deployed service is then `{dir}/{app_name}`

Optional parameters:

- `host_uv_path`: Path to the `uv` on the remote server. Since `uv` is often times installed in `~/.cargo/bin` or other location that is only added to the `$PATH` by using a login shell, this option allows to specify the custom path, since this tool doesn't source any of the dotfiles when connecting via SSH.
- `ignore_list`: List of files and directories to ignore when copying files to the remote server. Files not in git are automatically ignored, as well as those listed in `.gitignore`

### Configuring via pyproject.toml section

Here's an example config in the `pyproject.toml` file, with both required and optional values:

    [tool.deploy]
    host = "me@myhost"
    dir = "/home/appuser/myapps"
    app_name = "demo_service"
    host_uv_path = "/home/appuser/.cargo/bin/uv"
    ignore_list = [
        "devenv.*",
        "README.md",
        ".envrc",
        "data",
        "test",
        ".direnv",
        ".devenv",
    ]


### Configuring via environment variables

Configuration parameters can also be passed in via environment variables, in which case they take precedence over the values from the `pyproject.toml` file. Values can also be mixed and matched.

If passing in parameters via env variables, prefix them with `DEPLOY_`, eg:

    DEPLOY_HOST=myserver2 uv run deploy.py

## Testing

Currently end-to-end tests only, which connect to a server and do a deployment of the `demo_service` in this repo, run with:

    DEPLOY_HOST=myserver DEPLOY_DIR=/tmp/apps DEPLOY_APP_NAME=demo_service uv run pytest test.py

## Rationale

I have a bunch of small Python services and API's I'm hosting on my own server within a VPN and I wanted a simple and quick solution to deploy/redeploy those tools. The closest project to what I wanted is [piku](https://github.com/piku/piku) which I gave a shot, but I didn't like some things it does, such as: using nginx (I don't need a webserver in most cases, and when I do, I prefer `Caddy`), using `virtualenv` (I prefer `uv`), requires a bunch of system level packages ([listed here](https://piku.github.io/install/INSTALL-ubuntu-22.04-jammy.html)), and uses `uWSGI` (besides the fact that `uWSGI` is in maintenance mode, I wanted a way to use my own *SGI webserver). On top of it, `piku` supports a lot more languages that I don't use.

Anything involving Docker I discarded immediately as too heavy for my use case.

This is something I came up with to address the need for a simple deployment to a single server - I would not uses this to deploy to a fleet.

I don't see this evolving much past the scope that's already in there, but there are some things that would probably be nice to have, so these will likely be added over time:

- better status reporting - more output during deployment so it's clear what's happening
- improved error reporting - it's a bit hard to see what's happening when something fails
- compressing files before upload - currently, files are uploaded one-by-one, which can take a bit depending on the size of the project and latency to the server
- basic observability commands like `status` (would read from `systemctl status`), `logs` (would read from `journalctl`)
- rollbacks - could be useful to have, eg. by specifying the git SHA of the commit to which to rollback to
