"""Every target the bench can deploy to.

Adding a target means one entry here, a directory under targets/ with deploy.sh
and destroy.sh, an ADR under docs/adr/, and a passing contract on a real deploy.

The sizes are the closest each provider offers to one small instance; they are
not identical, and the record keeps the exact size so a reader can see that.
Every target is held to one instance so throughput compares one instance with
another, not one provider's autoscaler with another's.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    id: str
    provider: str
    region: str
    region_label: str
    size: str
    scale_to_zero: bool
    # "image": deploys the digest built by the bench workflow.
    # "source": the provider builds the same Dockerfile at the same commit itself.
    artifact: str
    # Environment the deploy script needs (secrets and repository variables).
    requires: tuple[str, ...]
    # Environment destroy.sh needs; cleanup must not depend on deploy-only inputs.
    cleanup_requires: tuple[str, ...]
    adr: str


TARGETS: dict[str, Target] = {
    t.id: t
    for t in (
        Target(
            id="railway",
            provider="Railway",
            region="asia-southeast1-eqsg3a",
            region_label="Singapore",
            size="usage-based; 1 replica, no CPU/RAM cap set",
            scale_to_zero=False,
            artifact="source",
            requires=("RAILWAY_TOKEN", "RAILWAY_SERVICE", "RAILWAY_URL"),
            cleanup_requires=("RAILWAY_TOKEN", "RAILWAY_SERVICE"),
            adr="docs/adr/ADR-0003-railway.md",
        ),
        Target(
            id="render",
            provider="Render",
            region="singapore",
            region_label="Singapore",
            size="starter (0.5 CPU, 512 MB), 1 instance",
            scale_to_zero=False,
            artifact="image",
            requires=("RENDER_API_KEY", "RENDER_OWNER_ID"),
            cleanup_requires=("RENDER_API_KEY", "RENDER_OWNER_ID"),
            adr="docs/adr/ADR-0004-render.md",
        ),
        Target(
            id="fly",
            provider="Fly.io",
            region="sin",
            region_label="Singapore",
            size="shared-cpu-1x, 512 MB, 1 machine",
            scale_to_zero=True,
            artifact="image",
            requires=("FLY_API_TOKEN", "FLY_ORG"),
            cleanup_requires=("FLY_API_TOKEN", "FLY_ORG"),
            adr="docs/adr/ADR-0005-fly.md",
        ),
        Target(
            id="cloudrun",
            provider="Google Cloud Run",
            region="asia-southeast1",
            region_label="Singapore",
            size="1 vCPU, 512 MiB, max 1 instance, request-based billing",
            scale_to_zero=True,
            artifact="image",
            requires=("GCP_PROJECT", "BENCH_IMAGE_GCP"),
            cleanup_requires=("GCP_PROJECT",),
            adr="docs/adr/ADR-0006-cloud-run.md",
        ),
    )
}
