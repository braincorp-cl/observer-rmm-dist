from rest_framework.serializers import ModelSerializer
from .models import ReportSchedule


class ReportScheduleAuditSerializer(ModelSerializer):
    class Meta:
        model = ReportSchedule
        fields = [
            "name",
            "enabled",
            "report_template",
            "format",
            "schedule",
            "email_recipients",
            "send_report_email",
            "email_settings",
            "timezone",
        ]
