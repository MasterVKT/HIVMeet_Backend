"""Back-office d'administration HIVMeet.

Application Django *isolée* : elle n'est jamais chargée par l'API mobile
(``hivmeet_backend.settings``) et ne modifie aucun fichier de l'application.
Elle s'exécute uniquement avec ``backoffice.conf.settings``.
"""
