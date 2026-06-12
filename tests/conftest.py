"""Shared pytest configuration."""

import pytest

from tests.e2e_fixtures import configure_compose_env, run_migrations


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: end-to-end tests requiring Docker (testcontainers)",
    )


@pytest.fixture(scope="module")
def e2e_stack():
    import os

    if os.environ.get("STARSCREAM_E2E_COMPOSE") == "1":
        configure_compose_env()
        from starscream.health import check_dependencies

        health = check_dependencies()
        if not health["all_ok"]:
            pytest.skip(f"compose services not ready: {health['dependencies']}")
        run_migrations()
        from starscream.seed.bootstrap import run_seed
        from tests.e2e_fixtures import clear_e2e_caches

        run_seed()
        clear_e2e_caches()
        yield
        return

    pytest.importorskip("testcontainers")
    from tests.e2e_fixtures import _docker_available, clear_e2e_caches

    if not _docker_available():
        pytest.skip("Docker is not available")

    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    postgres = (
        DockerContainer("postgis/postgis:16-3.4")
        .with_env("POSTGRES_USER", "starscream")
        .with_env("POSTGRES_PASSWORD", "starscream")
        .with_env("POSTGRES_DB", "starscream")
        .with_exposed_ports(5432)
    )
    meili = (
        DockerContainer("getmeili/meilisearch:v1.11")
        .with_env("MEILI_ENV", "development")
        .with_env("MEILI_NO_ANALYTICS", "true")
        .with_exposed_ports(7700)
    )
    minio = (
        DockerContainer("minio/minio:latest")
        .with_command("server /data --console-address :9001")
        .with_env("MINIO_ROOT_USER", "starscream")
        .with_env("MINIO_ROOT_PASSWORD", "starscream")
        .with_exposed_ports(9000)
    )

    postgres.start()
    meili.start()
    minio.start()

    try:
        wait_for_logs(postgres, "ready to accept connections", timeout=60)
        wait_for_logs(meili, "Server listening", timeout=60)
        wait_for_logs(minio, "MinIO Object Storage Server", timeout=60)

        pg_host = postgres.get_container_host_ip()
        pg_port = postgres.get_exposed_port(5432)
        meili_host = meili.get_container_host_ip()
        meili_port = meili.get_exposed_port(7700)
        minio_host = minio.get_container_host_ip()
        minio_port = minio.get_exposed_port(9000)

        os.environ["DATABASE_URL"] = (
            f"postgresql+psycopg://starscream:starscream@{pg_host}:{pg_port}/starscream"
        )
        os.environ["MEILISEARCH_URL"] = f"http://{meili_host}:{meili_port}"
        os.environ["MEILISEARCH_API_KEY"] = ""
        os.environ["S3_ENDPOINT"] = f"http://{minio_host}:{minio_port}"
        os.environ["S3_ACCESS_KEY"] = "starscream"
        os.environ["S3_SECRET_KEY"] = "starscream"
        os.environ["S3_BUCKET"] = "starscream-audio"
        os.environ["S3_REGION"] = "us-east-1"
        os.environ["ENRICH_GEOCODE"] = "false"
        os.environ["ENRICH_HABITAT"] = "false"
        os.environ["ENRICH_WEATHER"] = "false"
        os.environ["ENRICH_OSM"] = "false"

        clear_e2e_caches()
        run_migrations()

        from starscream.seed.bootstrap import run_seed

        run_seed()
        clear_e2e_caches()

        yield
    finally:
        minio.stop()
        meili.stop()
        postgres.stop()
