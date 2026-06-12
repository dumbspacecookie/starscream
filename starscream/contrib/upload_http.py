import httpx

from starscream.contrib.batch import BatchUploadResult, ContributionPackage


def upload_package_http(
    pkg: ContributionPackage,
    *,
    api_base: str,
    timeout: float = 120.0,
) -> BatchUploadResult:
    url = api_base.rstrip("/") + "/v1/contrib/upload"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                data={"manifest_json": pkg.manifest.model_dump_json()},
                files={
                    "audio": (
                        pkg.manifest.audio_filename,
                        pkg.audio_path.read_bytes(),
                        "audio/wav",
                    )
                },
            )
    except httpx.HTTPError as exc:
        return BatchUploadResult(
            manifest_path=str(pkg.manifest_path),
            title=pkg.manifest.title,
            status="failed",
            errors=[str(exc)],
        )

    if response.status_code == 201:
        body = response.json()
        return BatchUploadResult(
            manifest_path=str(pkg.manifest_path),
            title=pkg.manifest.title,
            status="uploaded",
            recording_id=body["recording"]["id"],
            warnings=body.get("warnings", []),
        )

    detail = response.text
    try:
        detail = response.json().get("detail", detail)
    except Exception:
        pass
    errors = detail if isinstance(detail, list) else [str(detail)]
    return BatchUploadResult(
        manifest_path=str(pkg.manifest_path),
        title=pkg.manifest.title,
        status="failed",
        errors=errors if isinstance(errors, list) else [str(errors)],
    )
