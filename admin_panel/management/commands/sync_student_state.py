"""Django management command to set Student.state from user data (inferred registration step)."""
from django.core.management.base import BaseCommand

from admin_panel.models import Student
from bot.services import StudentService


class Command(BaseCommand):
    help = (
        "Set Student.state for each student based on their filled fields (initial_full_name, "
        "phone_number, first_name, etc.). Use after deployment or to backfill the state column."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be updated, do not save.",
        )
        parser.add_argument(
            "--telegram-id",
            type=int,
            default=None,
            help="Process only this student (telegram_id). Default: all students.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        telegram_id = options.get("telegram_id")

        qs = Student.objects.all()
        if telegram_id is not None:
            qs = qs.filter(telegram_id=telegram_id)
        qs = qs.select_related("parent", "teacher", "registration_source")

        total = 0
        updated = 0
        for student in qs:
            total += 1
            inferred = StudentService.infer_registration_state_from_student(student)
            if inferred != student.state:
                self.stdout.write(
                    f"  telegram_id={student.telegram_id}: state {student.state!r} -> {inferred!r}"
                )
                if not dry_run:
                    student.state = inferred
                    student.save(update_fields=["state"])
                updated += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would update {updated} of {total} student(s). Run without --dry-run to apply."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Updated state for {updated} of {total} student(s).")
            )
