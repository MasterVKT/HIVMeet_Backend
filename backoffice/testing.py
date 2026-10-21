"""Exécuteur de tests du back-office : par défaut, uniquement ``backoffice``."""

from django.test.runner import DiscoverRunner


class BackofficeDiscoverRunner(DiscoverRunner):
    default_test_labels = ('backoffice',)

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        labels = tuple(test_labels or self.default_test_labels)
        return super().build_suite(labels, extra_tests=extra_tests, **kwargs)
