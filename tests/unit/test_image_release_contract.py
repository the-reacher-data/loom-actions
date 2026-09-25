"""Contract tests for the reusable image release.

It publishes exactly the release it is given: a version that is not
``X.Y.Z`` stops it before anything is built, the image is built from the
release tag rather than whatever commit started the run, and in a public
repository the pushed digest gets a build provenance attestation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import workflow_steps as wf

NAME = "image-release"
GUARD = "Require a release version"
CREDENTIALS = "Require the Docker Hub credentials"
ANCESTRY = "Require the release commit on the default branch"
LATEST = "Decide whether latest moves"
PUBLIC = "!github.event.repository.private"


def _uses(fragment: str) -> dict[str, object]:
    return next(s for s in wf.steps(NAME, "image") if fragment in s.get("uses", ""))


def _outputs(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())


class TestInputs:
    @pytest.mark.parametrize("name", ["version", "ghcr-image"])
    def test_the_release_is_required(self, name: str) -> None:
        assert wf.call(NAME)["inputs"][name]["required"] is True

    @pytest.mark.parametrize(
        ("name", "default"),
        [
            ("dockerhub-image", ""),
            ("platforms", "linux/amd64"),
            ("image-context", "."),
            ("dockerfile", "Dockerfile"),
            ("expected-sha", ""),
        ],
    )
    def test_optional_inputs_keep_their_defaults(self, name: str, default: object) -> None:
        declared = wf.call(NAME)["inputs"][name]
        assert declared["required"] is False
        assert declared["default"] == default

    @pytest.mark.parametrize("secret", ["DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN"])
    def test_the_docker_hub_secrets_are_optional(self, secret: str) -> None:
        assert wf.call(NAME)["secrets"][secret]["required"] is False

    def test_it_returns_the_digest(self) -> None:
        assert wf.call(NAME)["outputs"]["digest"]["value"] == "${{ jobs.image.outputs.digest }}"


class TestPermissions:
    def test_the_job_gets_only_what_publishing_needs(self) -> None:
        assert wf.jobs(NAME)["image"]["permissions"] == {
            "contents": "read",
            "packages": "write",
            "id-token": "write",
            "attestations": "write",
        }


class TestOrder:
    def test_the_version_guard_runs_first(self) -> None:
        assert wf.steps(NAME, "image")[0]["name"] == GUARD

    def test_the_credentials_guard_runs_before_any_login(self) -> None:
        titles = [s.get("name") or s.get("uses") for s in wf.steps(NAME, "image")]
        first_login = next(i for i, t in enumerate(titles) if "login-action" in str(t))
        assert titles.index(CREDENTIALS) < first_login

    def test_the_release_tag_is_checked_out_with_every_tag_and_branch(self) -> None:
        checkout = _uses("actions/checkout")
        assert checkout["with"] == {
            "ref": "refs/tags/v${{ inputs.version }}",
            "fetch-depth": 0,
            "persist-credentials": False,
        }

    def test_the_commit_and_latest_are_decided_before_any_login(self) -> None:
        titles = [s.get("name") or s.get("uses") for s in wf.steps(NAME, "image")]
        first_login = next(i for i, t in enumerate(titles) if "login-action" in str(t))
        assert titles.index(ANCESTRY) < first_login
        assert titles.index(LATEST) < first_login


class TestPublish:
    def test_it_pushes_every_platform_with_sbom_and_provenance(self) -> None:
        build = _uses("docker/build-push-action")
        with_ = build["with"]
        assert isinstance(with_, dict)
        assert with_["push"] is True
        assert with_["platforms"] == "${{ inputs.platforms }}"
        assert with_["sbom"] is True
        assert with_["provenance"] == "mode=max"
        for arg in ("VERSION=", "REVISION=", "CREATED="):
            assert arg in with_["build-args"]

    def test_the_three_tags_are_published(self) -> None:
        meta = _uses("docker/metadata-action")
        with_ = meta["with"]
        assert isinstance(with_, dict)
        tags = str(with_["tags"])
        assert "type=raw,value=${{ steps.version.outputs.version }}" in tags
        assert "type=raw,value=${{ steps.version.outputs.minor }}" in tags
        assert "type=raw,value=latest,enable=${{ steps.latest.outputs.latest == 'true' }}" in tags
        assert with_["flavor"] == "latest=false"

    def test_the_release_reads_no_shared_layer_cache(self) -> None:
        text = (wf.WORKFLOWS / f"{NAME}.yml").read_text("utf-8")
        assert "scope=image" not in text
        assert "type=gha" not in text
        build = _uses("docker/build-push-action")["with"]
        assert isinstance(build, dict)
        assert "cache-from" not in build
        assert "cache-to" not in build

    def test_the_builder_images_are_pinned_by_digest(self) -> None:
        qemu = _uses("docker/setup-qemu-action")
        buildx = _uses("docker/setup-buildx-action")
        assert str(qemu["with"]["image"]).startswith("docker.io/tonistiigi/binfmt@sha256:")
        assert str(buildx["with"]["driver-opts"]).startswith("image=moby/buildkit@sha256:")
        assert qemu["if"] == "${{ steps.version.outputs.qemu == 'true' }}"

    def test_docker_hub_is_opt_in(self) -> None:
        login = [s for s in wf.steps(NAME, "image") if "login-action" in s.get("uses", "")]
        hub = [s for s in login if "docker.io" in str(s["with"].get("registry", "docker.io"))]
        assert len(login) == 2
        assert hub[0]["if"] == "${{ inputs.dockerhub-image != '' }}"

    def test_the_ghcr_digest_is_attested_in_public(self) -> None:
        attest = [
            s for s in wf.steps(NAME, "image") if "attest-build-provenance" in s.get("uses", "")
        ]
        ghcr = attest[0]
        assert PUBLIC in ghcr["if"]
        assert ghcr["with"] == {
            "subject-name": "${{ inputs.ghcr-image }}",
            "subject-digest": "${{ steps.build.outputs.digest }}",
            "push-to-registry": True,
            "create-storage-record": False,
        }

    def test_a_private_repository_gets_a_notice(self) -> None:
        notice = wf.step(NAME, "image", "Skip the attestation in a private repository")
        assert notice["if"] == "${{ github.event.repository.private }}"
        assert "::notice" in notice["run"]


class TestVersionGuard:
    def _guard(
        self, tmp_path: Path, version: str, image: str = "ghcr.io/acme/app"
    ) -> tuple[int, dict[str, str]]:
        output = tmp_path / "out.txt"
        output.touch()
        env = {
            "VERSION": version,
            "GHCR_IMAGE": image,
            "PLATFORMS": "linux/amd64",
            "GITHUB_OUTPUT": str(output),
        }
        done = wf.run(NAME, "image", GUARD, env, tmp_path)
        return done.returncode, _outputs(output)

    def test_a_release_version_passes_with_its_minor(self, tmp_path: Path) -> None:
        code, outputs = self._guard(tmp_path, "1.12.3")
        assert code == 0
        assert outputs["version"] == "1.12.3"
        assert outputs["minor"] == "1.12"
        assert outputs["created"].endswith("Z")

    @pytest.mark.parametrize("version", ["", "v1.2.3", "1.2", "1.2.3-rc.1", "1.2.3\n", "01.2.x"])
    def test_anything_else_fails(self, tmp_path: Path, version: str) -> None:
        code, outputs = self._guard(tmp_path, version)
        assert code != 0
        assert outputs == {}

    @pytest.mark.parametrize(
        "image", ["docker.io/acme/app", "ghcr.io/Acme/app", "ghcr.io/acme/app:1"]
    )
    def test_a_ghcr_image_must_be_a_lowercase_ghcr_name(self, tmp_path: Path, image: str) -> None:
        code, _ = self._guard(tmp_path, "1.2.3", image)
        assert code != 0


class TestCredentialsGuard:
    @pytest.mark.parametrize(
        ("image", "user", "token", "code"),
        [
            ("", "", "", 0),
            ("acme/app", "u", "t", 0),
            ("acme/app", "", "t", 1),
            ("acme/app", "u", "", 1),
        ],
    )
    def test_docker_hub_needs_both_secrets(
        self, tmp_path: Path, image: str, user: str, token: str, code: int
    ) -> None:
        env = {"DOCKERHUB_IMAGE": image, "DOCKERHUB_USERNAME": user, "DOCKERHUB_TOKEN": token}
        assert wf.run(NAME, "image", CREDENTIALS, env, tmp_path).returncode == code


class TestQemu:
    @pytest.mark.parametrize(
        ("platforms", "qemu"),
        [
            ("linux/amd64", "false"),
            (" linux/amd64 ", "false"),
            ("linux/amd64,linux/arm64", "true"),
            ("linux/arm64", "true"),
            ("linux/amd64, linux/amd64", "false"),
        ],
    )
    def test_qemu_only_for_a_foreign_platform(
        self, tmp_path: Path, platforms: str, qemu: str
    ) -> None:
        output = tmp_path / "out.txt"
        output.touch()
        env = {
            "VERSION": "1.2.3",
            "GHCR_IMAGE": "ghcr.io/acme/app",
            "PLATFORMS": platforms,
            "GITHUB_OUTPUT": str(output),
        }
        assert wf.run(NAME, "image", GUARD, env, tmp_path).returncode == 0
        assert _outputs(output)["qemu"] == qemu


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ("git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args),
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """master: A - B - C, tagged v1.0.0 (A), v1.1.0 (B), v2.0.0 (C); a side branch off A."""
    path = tmp_path / "repo"
    path.mkdir()
    _git(path, "init", "-q", "-b", "master")
    for message, tag in (("a", "v1.0.0"), ("b", "v1.1.0"), ("c", "v2.0.0")):
        _commit(path, message)
        _git(path, "tag", tag)
    _git(path, "update-ref", "refs/remotes/origin/master", "HEAD")
    _git(path, "checkout", "-q", "-b", "side", "v1.0.0")
    _commit(path, "side")
    _git(path, "tag", "v1.0.1")
    _git(path, "checkout", "-q", "v1.1.0")
    _commit(path, "hotfix on the old line")
    _git(path, "tag", "v1.1.1")
    _git(path, "checkout", "-q", "master")
    return path


def _run_in(repo: Path, title: str, tag: str, **env: str) -> tuple[int, str, dict[str, str]]:
    _git(repo, "checkout", "-q", tag)
    output = repo.parent / "out.txt"
    output.write_text("", encoding="utf-8")
    done = wf.run(NAME, "image", title, {"GITHUB_OUTPUT": str(output), **env}, repo)
    return done.returncode, done.stdout, _outputs(output)


class TestReleaseCommit:
    def _check(self, repo: Path, tag: str, expected: str = "", branch: str = "master"):
        return _run_in(repo, ANCESTRY, tag, DEFAULT_BRANCH=branch, EXPECTED_SHA=expected)

    def test_a_tag_on_the_default_branch_passes(self, repo: Path) -> None:
        code, _, outputs = self._check(repo, "v1.1.0")
        assert code == 0
        assert outputs["sha"] == _git(repo, "rev-parse", "v1.1.0^{commit}")

    def test_a_tag_off_the_default_branch_fails(self, repo: Path) -> None:
        code, stdout, outputs = self._check(repo, "v1.0.1")
        assert code != 0
        assert "::error" in stdout
        assert outputs == {}

    def test_the_expected_commit_must_match(self, repo: Path) -> None:
        wanted = _git(repo, "rev-parse", "v2.0.0^{commit}")
        assert self._check(repo, "v2.0.0", wanted)[0] == 0
        code, stdout, _ = self._check(repo, "v1.1.0", wanted)
        assert code != 0
        assert "::error" in stdout

    @pytest.mark.parametrize("branch", ["", "main"])
    def test_an_unknown_default_branch_fails(self, repo: Path, branch: str) -> None:
        assert self._check(repo, "v1.1.0", branch=branch)[0] != 0


class TestLatest:
    @pytest.mark.parametrize(
        ("tag", "latest"),
        [("v2.0.0", "true"), ("v1.1.1", "false"), ("v1.0.0", "false")],
    )
    def test_latest_moves_only_for_the_highest_version(
        self, repo: Path, tag: str, latest: str
    ) -> None:
        code, _, outputs = _run_in(repo, LATEST, tag, VERSION=tag.removeprefix("v"))
        assert code == 0
        assert outputs["latest"] == latest

    def test_a_higher_patch_beats_a_lexically_higher_one(self, repo: Path) -> None:
        _git(repo, "tag", "v2.0.10", "v2.0.0")
        _git(repo, "tag", "v2.0.9", "v2.0.0")
        _git(repo, "tag", "v2.1.0-rc.1", "v2.0.0")
        code, _, outputs = _run_in(repo, LATEST, "v2.0.10", VERSION="2.0.10")
        assert code == 0
        assert outputs["latest"] == "true"
