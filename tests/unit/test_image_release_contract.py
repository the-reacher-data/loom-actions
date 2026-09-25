"""Contract tests for the reusable image release.

It publishes exactly the release it is given: a version that is not
``X.Y.Z`` stops it before anything is built, the image is built from the
release tag rather than whatever commit started the run, and in a public
repository the pushed digest gets a build provenance attestation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import workflow_steps as wf

NAME = "image-release"
GUARD = "Require a release version"
CREDENTIALS = "Require the Docker Hub credentials"
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

    def test_the_release_tag_is_checked_out(self) -> None:
        checkout = _uses("actions/checkout")
        assert checkout["with"] == {
            "ref": "refs/tags/v${{ inputs.version }}",
            "persist-credentials": False,
        }


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
        assert "type=raw,value=latest" in tags
        assert with_["flavor"] == "latest=false"

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
        env = {"VERSION": version, "GHCR_IMAGE": image, "GITHUB_OUTPUT": str(output)}
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
