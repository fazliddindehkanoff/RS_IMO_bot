"""Dashboard callback and metrics for admin index."""
from .models import (
    Certificate,
    Parent,
    Student,
    Teacher,
    Test,
    TestAttempt,
)


def dashboard_callback(request, context):
    """Add dashboard metrics to admin index context."""
    context["students_total"] = Student.objects.count()
    context["students_active"] = Student.objects.filter(is_active=True).count()
    context["teachers_count"] = Teacher.objects.count()
    context["parents_count"] = Parent.objects.count()
    context["tests_total"] = Test.objects.count()
    context["tests_active"] = Test.objects.filter(is_active=True).count()
    context["test_attempts_total"] = TestAttempt.objects.count()
    context["test_attempts_pending"] = TestAttempt.objects.filter(
        status="PENDING"
    ).count()
    context["test_attempts_submitted"] = TestAttempt.objects.filter(
        status="SUBMITTED_FINAL"
    ).count()
    context["certificates_count"] = Certificate.objects.count()
    context["recent_test_attempts"] = (
        TestAttempt.objects.select_related("student", "test")
        .order_by("-created_at")[:10]
    )
    return context
