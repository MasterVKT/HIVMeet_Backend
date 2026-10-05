"""Safe default test discovery for the HIVMeet Django project.

The repository also contains manually-invoked ``test_e2e_*.py`` diagnostic
scripts at its root.  Standard unittest discovery imports every matching
module, so running ``manage.py test`` without labels used to execute those
scripts during collection.  Apart from making the suite non-deterministic,
that could print credentials and profile data before Django's test isolation
was active.

Explicit labels are preserved unchanged.  Only the no-label default is scoped
to actual Django test packages.
"""

from django.test.runner import DiscoverRunner


class HIVMeetDiscoverRunner(DiscoverRunner):
    """Discover supported app/package tests, excluding manual root scripts."""

    default_test_labels = (
        'authentication',
        'profiles',
        'matching',
        'messaging',
        'notifications',
        'subscriptions',
        'resources',
        'hivmeet_backend.test_logging_privacy',
        'tests',
    )

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        labels = tuple(test_labels or self.default_test_labels)
        return super().build_suite(
            labels,
            extra_tests=extra_tests,
            **kwargs,
        )
