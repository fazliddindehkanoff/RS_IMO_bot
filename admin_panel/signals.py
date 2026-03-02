import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from admin_panel.models import TestQuestion, TestAnswer, TestAttempt

logger = logging.getLogger(__name__)

# To track changes between pre_save and post_save, we attach the original values
# Note: A better approach in heavily concurrent envs would be to use a dict mapping
# `id` to the state, but since these are modified strictly via the admin interface
# one at a time sequentially, this approach is usually acceptable.
# A robust way is attaching the original state to the instance object itself.

@receiver(pre_save, sender=TestQuestion)
def store_original_test_question(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_obj = TestQuestion.objects.get(pk=instance.pk)
            instance._old_correct_answer = old_obj.correct_answer
            instance._old_ball_weight = old_obj.ball_weight
        except TestQuestion.DoesNotExist:
            instance._old_correct_answer = None
            instance._old_ball_weight = None
    else:
        instance._old_correct_answer = None
        instance._old_ball_weight = None


@receiver(post_save, sender=TestQuestion)
def update_answers_on_question_change(sender, instance, created, **kwargs):
    if created:
        return

    old_correct_answer = getattr(instance, '_old_correct_answer', None)
    old_ball_weight = getattr(instance, '_old_ball_weight', None)

    if (old_correct_answer is not None and old_correct_answer != instance.correct_answer) or \
       (old_ball_weight is not None and old_ball_weight != instance.ball_weight):
        
        logger.info(f"TestQuestion {instance.pk} updated. Recalculating related answers and attempts.")
        
        # 1. Update all TestAnswers for this question
        answers_to_update = TestAnswer.objects.filter(question=instance)
        updated_answers = []
        
        for answer in answers_to_update:
            # Recalculate correctness and points for this answer
            # If the student didn't pick an answer, choice might be None or empty
            if answer.answer_choice:
                is_correct = (answer.answer_choice == instance.correct_answer)
                points_earned = instance.ball_weight if is_correct else 0.0
            else:
                is_correct = False
                points_earned = 0.0

            # Only update if there was an actual change to avoid unnecessary DB writes
            if answer.is_correct != is_correct or answer.points_earned != points_earned:
                answer.is_correct = is_correct
                answer.points_earned = points_earned
                updated_answers.append(answer)

        if updated_answers:
            TestAnswer.objects.bulk_update(updated_answers, ['is_correct', 'points_earned'])
            logger.info(f"Updated {len(updated_answers)} TestAnswers for TestQuestion {instance.pk}.")

        # 2. Update affected TestAttempts
        # Find all attempts that were touched by these answers
        affected_attempt_ids = set()
        for ans in answers_to_update:
            affected_attempt_ids.add(ans.attempt_id)

        if affected_attempt_ids:
            attempts_to_update = TestAttempt.objects.filter(id__in=affected_attempt_ids).prefetch_related('answers__question')
            updated_attempts = []
            
            for attempt in attempts_to_update:
                total_earned = 0.0
                total_possible = 0.0
                
                # Recalculate totals from all answers associated with this attempt
                for ans in attempt.answers.all():
                    total_earned += ans.points_earned
                    total_possible += ans.question.ball_weight
                
                score = (total_earned / total_possible * 100) if total_possible > 0 else 0.0
                
                # Only update if changed
                if attempt.earned_points != total_earned or attempt.total_points != total_possible or attempt.score != score:
                    attempt.earned_points = total_earned
                    attempt.total_points = total_possible
                    attempt.score = score
                    updated_attempts.append(attempt)
                    
            if updated_attempts:
                TestAttempt.objects.bulk_update(updated_attempts, ['earned_points', 'total_points', 'score'])
                logger.info(f"Recalculated {len(updated_attempts)} TestAttempts due to TestQuestion {instance.pk} update.")
