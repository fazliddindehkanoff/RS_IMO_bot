"""Django management command to duplicate a test with all its questions across grades and/or languages."""
from django.core.management.base import BaseCommand
from admin_panel.models import Test, TestQuestion
import shutil
import os


class Command(BaseCommand):
    help = "Duplicate a test with all its questions across grades and/or languages"

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-id',
            type=int,
            help='ID of the test to duplicate'
        )
        parser.add_argument(
            '--test-title',
            type=str,
            help='Title of the test to duplicate (alternative to --test-id)'
        )
        parser.add_argument(
            '--by-grades',
            action='store_true',
            help='Duplicate for all grades (5, 6, 7, 8)'
        )
        parser.add_argument(
            '--by-languages',
            action='store_true',
            help='Duplicate for all languages (uz, ru, en)'
        )
        parser.add_argument(
            '--target-grade',
            type=int,
            help='Specific target grade to duplicate the test to'
        )
        parser.add_argument(
            '--new-title',
            type=str,
            help='Title for the new test (if not using --by-grades or --by-languages)'
        )

    def duplicate_test_and_questions(self, original_test, new_test):
        """Helper method to duplicate all questions from one test to another."""
        questions = original_test.questions.all().order_by('question_number')
        
        if not questions.exists():
            self.stdout.write(self.style.WARNING(f"⚠️  Original test has no questions"))
            return 0
        
        copied_count = 0
        for question in questions:
            # Create new question with same attributes
            new_question = TestQuestion.objects.create(
                test=new_test,
                question_number=question.question_number,
                text=question.text,
                option_a=question.option_a,
                option_b=question.option_b,
                option_c=question.option_c,
                option_d=question.option_d,
                correct_answer=question.correct_answer,
                ball_weight=question.ball_weight,
            )
            
            # Copy image if exists
            if question.image:
                try:
                    source_path = question.image.path
                    
                    if os.path.exists(source_path):
                        filename = os.path.basename(source_path)
                        dest_filename = f"questions/q{new_question.id}_{filename}"
                        dest_path = os.path.join('media', dest_filename)
                        
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                        
                        new_question.image = dest_filename
                        new_question.save()
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Could not copy image for question {question.question_number}: {e}")
                    )
            
            copied_count += 1
        
        return copied_count

    def handle(self, *args, **options):
        # Get test to duplicate
        test_id = options.get('test_id')
        test_title = options.get('test_title')
        by_grades = options.get('by_grades')
        by_languages = options.get('by_languages')
        new_title = options.get('new_title')
        target_grade = options.get('target_grade')
        
        # Find original test
        if test_id:
            try:
                original_test = Test.objects.get(id=test_id)
            except Test.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Test with ID {test_id} not found"))
                return
        elif test_title:
            try:
                original_test = Test.objects.get(title=test_title)
            except Test.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Test with title '{test_title}' not found"))
                return
        else:
            # List available tests
            tests = Test.objects.all()
            if not tests.exists():
                self.stdout.write(self.style.ERROR("❌ No tests found in the database"))
                return
            
            self.stdout.write(self.style.SUCCESS("📋 Available tests:"))
            for test in tests:
                self.stdout.write(f"  ID: {test.id} - {test.title} (Grade: {test.get_grade_display() if test.grade else 'N/A'}, Language: {test.language})")
            
            test_id = int(input("\nEnter the ID of the test to duplicate: "))
            try:
                original_test = Test.objects.get(id=test_id)
            except Test.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Test with ID {test_id} not found"))
                return
            
            target_grade_str = input(f"Enter the target grade to duplicate to (leave empty to keep original: {original_test.grade}): ")
            if target_grade_str.strip():
                try:
                    target_grade = int(target_grade_str.strip())
                except ValueError:
                    self.stdout.write(self.style.ERROR("❌ Target grade must be an integer"))
                    return
        
        # Determine duplication strategy
        if by_grades or by_languages or target_grade is not None:
            # Duplicate by grades and/or languages
            grade_choices = [5, 6, 7, 8]
            language_choices = ['uz', 'ru', 'en']
            
            if target_grade is not None:
                grades_to_create = [target_grade]
            else:
                grades_to_create = grade_choices if by_grades else [original_test.grade]
                
            languages_to_create = language_choices if by_languages else [original_test.language]
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"🔄 Creating test '{original_test.title}' for:\n"
                    f"   Grades: {grades_to_create}\n"
                    f"   Languages: {languages_to_create}"
                )
            )
            
            created_tests = []
            total_questions = 0
            
            for grade in grades_to_create:
                for language in languages_to_create:
                    # Skip if test already exists with same grade and language
                    if Test.objects.filter(
                        title=original_test.title,
                        grade=grade,
                        language=language
                    ).exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠️  Test '{original_test.title}' already exists for "
                                f"{self._get_grade_display(grade)} - {self._get_language_display(language)}"
                            )
                        )
                        continue
                    
                    try:
                        # Create new test
                        new_test = Test.objects.create(
                            title=original_test.title,
                            grade=grade,
                            language=language,
                            duration_minutes=original_test.duration_minutes,
                            version=original_test.version,
                            is_active=original_test.is_active,
                            starts_at=original_test.starts_at,
                            finish_at=original_test.finish_at,
                        )
                        
                        # Copy target students
                        target_students = original_test.target_students.all()
                        if target_students.exists():
                            new_test.target_students.set(target_students)
                        
                        # Duplicate questions
                        questions_count = self.duplicate_test_and_questions(original_test, new_test)
                        total_questions += questions_count
                        
                        created_tests.append({
                            'id': new_test.id,
                            'title': new_test.title,
                            'grade': self._get_grade_display(grade),
                            'language': self._get_language_display(language),
                            'questions': questions_count
                        })
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✅ Created test for {self._get_grade_display(grade)} - "
                                f"{self._get_language_display(language)} (ID: {new_test.id}, {questions_count} questions)"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Error creating test for {grade}/{language}: {e}")
                        )
            
            if created_tests:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✨ Test duplication completed!\n"
                        f"   Original test: '{original_test.title}' (ID: {original_test.id})\n"
                        f"   Created {len(created_tests)} test variant(s) with {total_questions} questions total"
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("⚠️  No new tests were created"))
        
        else:
            # Simple duplication with new title
            if not new_title:
                new_title = input(f"Enter the title for the new test (original: '{original_test.title}'): ")
            
            if not new_title:
                self.stdout.write(self.style.ERROR("❌ New title cannot be empty"))
                return
            
            try:
                # Create new test with same attributes
                new_test = Test.objects.create(
                    title=new_title,
                    grade=original_test.grade,
                    language=original_test.language,
                    duration_minutes=original_test.duration_minutes,
                    version=original_test.version,
                    is_active=original_test.is_active,
                    starts_at=original_test.starts_at,
                    finish_at=original_test.finish_at,
                )
                
                # Copy target students
                target_students = original_test.target_students.all()
                if target_students.exists():
                    new_test.target_students.set(target_students)
                
                # Duplicate questions
                questions_count = self.duplicate_test_and_questions(original_test, new_test)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✨ Test duplication completed successfully!\n"
                        f"   Original test: '{original_test.title}' (ID: {original_test.id})\n"
                        f"   New test: '{new_test.title}' (ID: {new_test.id})\n"
                        f"   Duplicated {questions_count} question(s)"
                    )
                )
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error during duplication: {e}"))
    
    def _get_grade_display(self, grade):
        """Get display name for grade."""
        grade_map = {
            1: 'Gooo',
            5: '5-sinf',
            6: '6-sinf',
            7: '7-sinf',
            8: '8-sinf',
        }
        return grade_map.get(grade, f'Grade {grade}')
    
    def _get_language_display(self, lang):
        """Get display name for language."""
        lang_map = {
            'uz': 'Uzbek (O\'zbek)',
            'ru': 'Russian (Rus)',
            'en': 'English (Ingliz)',
        }
        return lang_map.get(lang, lang)
