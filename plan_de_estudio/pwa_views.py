import os

from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


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
