from django.urls import path, include, re_path
from allauth.socialaccount.providers.openid_connect.views import callback
from allauth.headless.socialaccount.views import RedirectToProviderView
from allauth.headless.base.views import ConfigView

# `views` queda importado a proposito aunque flake8 lo vea sin usar: las rutas
# `ssoproviders/*` que lo consumen estan comentadas mas abajo por la decision
# BrainCorp D-2026-06-01-SSO-DEFERRED. Quitarlo obligaria a reponerlo al
# reactivar SSO (ADR-013), y el import en si no tiene efecto observable.
from . import views  # noqa: F401

urlpatterns = [
    re_path(
        r"^oidc/(?P<provider_id>[^/]+)/",
        include(
            [
                path(
                    "login/callback/",
                    callback,
                    name="openid_connect_callback",
                ),
            ]
        ),
    ),
    # SSO deshabilitado por decisión BrainCorp D-2026-06-01-SSO-DEFERRED (mitiga GAP-024 / Q-SSO-03).
    # Para reactivar, materializar ADR-013 (sanitize response + forced overwrite) antes de descomentar.
    # path("ssoproviders/", views.GetAddSSOProvider.as_view()),
    # path("ssoproviders/<int:pk>/", views.GetUpdateDeleteSSOProvider.as_view()),
    # path("ssoproviders/token/", views.GetAccessToken.as_view()),
    # path("ssoproviders/settings/", views.GetUpdateSSOSettings.as_view()),
    # path("ssoproviders/account/", views.DisconnectSSOAccount.as_view()),
]

allauth_urls = [
    path(
        "browser/v1/",
        include(
            (
                [
                    path(
                        "config/",
                        ConfigView.as_api_view(client="browser"),
                        name="config",
                    ),
                    path(
                        "",
                        include(
                            (
                                [
                                    path(
                                        "auth/provider/redirect/",
                                        RedirectToProviderView.as_api_view(
                                            client="browser"
                                        ),
                                        name="redirect_to_provider",
                                    )
                                ],
                                "headless",
                            ),
                            namespace="socialaccount",
                        ),
                    ),
                ],
                "headless",
            ),
            namespace="browser",
        ),
    )
]
