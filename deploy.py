# /// script
# dependencies = [
#   "fabric",
#   "gitpython",
#   "pydantic-settings",
# ]
# ///

import os
import re
from typing import Tuple, Type

import invoke

from fabric import Connection
from git import Git
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict
)


class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (env_settings, PyprojectTomlConfigSettingsSource(settings_cls),)


class DeploySettings(Settings):
    """Config values from the [tool.deploy] section of the pyproject.toml"""

    host: str
    dir: str
    app_name: str
    host_uv_path: str | None = None
    ignore_list: list[str] = []

    model_config = SettingsConfigDict(
        pyproject_toml_table_header=('tool', 'deploy'),
        env_prefix="DEPLOY_",
    )


def _collect_files(toplevel_dir: str, ignore_list: list[str]):
    """Return a list of full paths to project files."""

    file_paths = []
    repo = Git(toplevel_dir)
    for f in repo.ls_files().split():
        if f.endswith("pyc"):
            continue

        add = True
        for ignore in ignore_list:
            if re.search(ignore, f):
                add = False
                break
        if add:
            file_paths.append(f)

    return file_paths


class Deploy:
    def __init__(self, settings: DeploySettings):
        self.conn = Connection(settings.host)
        self.dir = settings.dir
        self.app_name = settings.app_name
        self.app_path = os.path.join(settings.dir, settings.app_name)
        self.uv_path = settings.host_uv_path
        self.ignore_list = settings.ignore_list

    def _run_in_app_dir(self, cmd) -> invoke.runners.Result:
        """Run a command in the app dir."""

        return self.conn.run(f"cd {self.app_path} && {cmd}")

    def copy_files(self):
        """Copy files to the remote host."""

        files = _collect_files(".", self.ignore_list)
        for f in files:
            path = os.path.dirname(f)
            self.conn.run(f"mkdir -p {self.app_path}/{path}")
            self.conn.put(f, remote=os.path.join(self.app_path, path))
        self.conn.put("uv.lock", remote=self.app_path)

    def install_deps(self):
        """Install dependencies from the lock file."""

        if self.uv_path:
            self._run_in_app_dir(f"{self.uv_path} sync")
        else:
            self._run_in_app_dir("uv sync")

    def start_service(self):
        """Start the service on the remote host.

        Uses systemd in user mode to add and start a service defined
        in the service unit file.

        """
        self._run_in_app_dir(f"ln -sf {self.app_path}/{self.app_name}.service ~/.config/systemd/user/{self.app_name}.service && systemctl --user daemon-reload")
        self.conn.run(f"systemctl --user start {self.app_name}.service")
        self.conn.run(f"systemctl --user enable {self.app_name}.service")

    def deploy(self):
        self.copy_files()
        self.install_deps()
        self.start_service()

    def clean(self):
        """Cleans up the existing deployment.

        WARNING: This will remove the current app dir on the remote host!

        """
        # Stop the systemd job if there is one
        try:
            self.conn.run(f"systemctl --user stop {self.app_name}.service")
            print("Stopped the running service...")
        except invoke.exceptions.UnexpectedExit:
            # There was no systemd service to begin with
            pass

        self.conn.run(f"rm -rf {self.app_path}")


if __name__ == "__main__":
    settings = DeploySettings()
    d = Deploy(settings)
    d.clean()
    d.deploy()
