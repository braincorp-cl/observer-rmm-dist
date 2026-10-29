from django.urls import path

from erase import views

urlpatterns = [
    # Órdenes destructivas (gobernadas — despacho GATED por ADR-029)
    path("orders/", views.WipeOrderList.as_view()),
    path("agents/<str:agent_id>/orders/", views.WipeOrderCreate.as_view()),
    path("orders/<int:pk>/", views.WipeOrderDetail.as_view()),
    path("orders/<int:pk>/confirm/", views.WipeOrderConfirm.as_view()),
    path("orders/<int:pk>/cancel/", views.WipeOrderCancel.as_view()),
    # Plantillas de rutas para precargar una orden de wipe (feature 043)
    path("wipe-templates/", views.WipePathTemplateList.as_view()),
    # Recuperación de archivos (fileretrieval · B1 · no destructiva)
    path("fileretrieval/", views.FileRetrievalOrderList.as_view()),
    path(
        "agents/<str:agent_id>/fileretrieval/",
        views.FileRetrievalOrderCreate.as_view(),
    ),
    path("fileretrieval/<uuid:pk>/", views.FileRetrievalOrderDetail.as_view()),
    path("fileretrieval/<uuid:pk>/cancel/", views.FileRetrievalOrderCancel.as_view()),
    path(
        "fileretrieval/<uuid:pk>/files/<int:file_id>/download/",
        views.RetrievedFileDownload.as_view(),
    ),
    # Certificados (C)
    path("certificates/", views.EraseCertificateList.as_view()),
    path("certificates/<int:pk>/", views.EraseCertificateDetail.as_view()),
    path("certificates/<int:pk>/pdf/", views.EraseCertificatePDF.as_view()),
    path("certificates/<int:pk>/json/", views.EraseCertificateJSON.as_view()),
    # La clave PUBLICA de firma — sin auth: el destinatario de un certificado es
    # un tercero sin cuenta en la consola, y una clave publica no es un secreto.
    path("signing-key/", views.EraseSigningKey.as_view()),
    # Custodia (D)
    path("intake/", views.AssetIntakeList.as_view()),
    path("intake/<int:pk>/", views.AssetIntakeDetail.as_view()),
    path(
        "intake/<int:pk>/certify-destruction/",
        views.AssetIntakeCertifyDestruction.as_view(),
    ),
    # Cadena de custodia del activo (feature 053 · ola 2 · RF-06). Sin PUT,
    # PATCH ni DELETE: un eslabon es inmutable y se corrige anadiendo otro.
    path("intake/<int:pk>/custody/", views.IntakeCustodyEvents.as_view()),
    # Reconciliacion (RF-07). Autenticada SIEMPRE: enumerar bajas de un cliente
    # es justo lo que L-02 prohibio para el verificador publico.
    path("reconciliation/", views.ReconciliationReport.as_view()),
]
