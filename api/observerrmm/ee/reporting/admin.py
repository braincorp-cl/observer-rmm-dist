from django.contrib import admin

from .models import (
    ReportAsset,
    ReportTemplate,
    ReportDataQuery,
    ReportSchedule,
    ReportHistory,
)

admin.site.register(ReportTemplate)
admin.site.register(ReportAsset)
admin.site.register(ReportDataQuery)
admin.site.register(ReportSchedule)
admin.site.register(ReportHistory)
