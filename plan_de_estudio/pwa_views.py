import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

GITHUB_APK_VERSION_URL = (
    "https://github.com/ader999/plan_de_estudio/releases/latest/download/app-version.json"
)
GITHUB_APK_DOWNLOAD_URL = (
    "https://github.com/ader999/plan_de_estudio/releases/latest/download/PLANEAUML.apk"
)
APK_META_CACHE_TTL_SECONDS = 60
_apk_meta_cache = {"expires_at": 0.0, "data": None}


def clear_apk_metadata_cache():
    """Reset the in-memory APK version metadata cache."""
    _apk_meta_cache["expires_at"] = 0.0
    _apk_meta_cache["data"] = None


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_latest_apk_metadata(force_refresh=False):
    """Fetch and cache the latest compiled TWA APK version metadata."""
    now = time.monotonic()
    if not force_refresh and _apk_meta_cache["data"] and now < _apk_meta_cache["expires_at"]:
        return dict(_apk_meta_cache["data"])

    package_id = os.environ.get("ANDROID_PACKAGE_NAME", "com.planeauml.pwa").strip() or "com.planeauml.pwa"
    version_json_url = os.environ.get("APK_VERSION_JSON_URL", GITHUB_APK_VERSION_URL).strip()
    env_min_code = _safe_int(os.environ.get("APK_MIN_VERSION_CODE"), 0)
    env_version_name = os.environ.get("APK_LATEST_VERSION_NAME", "").strip()
    env_download_url = os.environ.get("APK_DOWNLOAD_URL", "").strip()

    remote_data = {}
    if version_json_url:
        try:
            req = Request(
                version_json_url,
                headers={"User-Agent": "PLANEAUML-AppVersionCheck/1.0", "Accept": "application/json"},
            )
            with urlopen(req, timeout=3.0) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    remote_data = parsed
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            remote_data = {}

    remote_code = _safe_int(remote_data.get("version_code"), 0)
    latest_code = max(remote_code, env_min_code, 1)
    available = remote_code > 0 or env_min_code > 0

    latest_name = (
        str(remote_data.get("version_name") or "").strip()
        or env_version_name
        or f"1.0.{latest_code}"
    )
    direct_apk_url = (
        env_download_url
        or str(remote_data.get("download_url") or "").strip()
        or GITHUB_APK_DOWNLOAD_URL
    )
    apk_size_bytes = _safe_int(remote_data.get("apk_size_bytes"), 0)
    apk_size_mb = round(apk_size_bytes / (1024 * 1024), 1) if apk_size_bytes > 0 else None

    metadata = {
        "latest_version_code": latest_code,
        "latest_version_name": latest_name,
        "package_id": str(remote_data.get("package_id") or package_id),
        "mandatory": bool(remote_data.get("mandatory", True)),
        "available": available,
        "download_url": "/app/descargar-apk/",
        "direct_apk_url": direct_apk_url,
        "release_tag": str(remote_data.get("release_tag") or ""),
        "commit_sha": str(remote_data.get("commit_sha") or ""),
        "built_at": str(remote_data.get("built_at") or ""),
        "apk_size_bytes": apk_size_bytes,
        "apk_size_mb": apk_size_mb,
    }

    _apk_meta_cache["data"] = dict(metadata)
    _apk_meta_cache["expires_at"] = now + APK_META_CACHE_TTL_SECONDS
    return metadata


@require_GET
def manifest_view(request):
    """Serve the Web App Manifest required for PWA installation and TWA APK builds."""
    manifest = {
        "id": "/",
        "name": "PLANEAUML - Planificación Académica",
        "short_name": "PLANEAUML",
        "description": (
            "Gestión de planes de estudio, sílabos, guías de estudio "
            "independiente y evaluación de eventos."
        ),
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#ebebeb",
        "theme_color": "#2563eb",
        "lang": "es",
        "icons": [
            {
                "src": static("img/pwa-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("img/pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("img/pwa-icon-512-maskable.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    return JsonResponse(
        manifest,
        content_type="application/manifest+json; charset=utf-8",
    )


@never_cache
@require_GET
def service_worker_view(request):
    """Serve the root-scoped Service Worker without aggressive HTTP caching."""
    response = render(
        request,
        "pwa/sw.js",
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@require_GET
def offline_view(request):
    """Render the standalone offline/slow-connection fallback page."""
    return render(request, "pwa/offline.html")


@require_GET
def assetlinks_view(request):
    """Serve Digital Asset Links for Android TWA verification when configured."""
    package_name = os.environ.get("ANDROID_PACKAGE_NAME", "com.planeauml.pwa").strip()
    raw_fingerprints = os.environ.get("ANDROID_ASSETLINKS_SHA256", "")
    fingerprints = [fp.strip() for fp in raw_fingerprints.split(",") if fp.strip()]

    if not fingerprints:
        return JsonResponse([], safe=False)

    payload = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package_name,
                "sha256_cert_fingerprints": fingerprints,
            },
        }
    ]
    return JsonResponse(payload, safe=False)


@never_cache
@require_GET
def app_version_view(request):
    """Return the latest compiled Android TWA APK metadata for mandatory update checks."""
    metadata = get_latest_apk_metadata()
    response = JsonResponse(metadata)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@never_cache
@require_GET
def app_download_view(request):
    """Redirect directly to the latest signed Android APK release artifact."""
    metadata = get_latest_apk_metadata()
    response = redirect(metadata["direct_apk_url"])
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
