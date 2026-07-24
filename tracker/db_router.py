class ClappiaRouter:
    """Routes the read-only ClappiaData model to the 'clappia' connection
    (the real, external server) -- every other model stays on 'default',
    which is where the app writes everything it owns (Dispatch,
    DispatchItem, status history, etc.)."""

    clappia_models = {'clappiadata'}

    def db_for_read(self, model, **hints):
        if model._meta.model_name in self.clappia_models:
            return 'clappia'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.model_name in self.clappia_models:
            return 'clappia'
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name in self.clappia_models:
            # managed=False already stops Django emitting DDL for it, but
            # this also keeps its migration state changes from being
            # considered against the 'default' connection's history.
            return db == 'clappia'
        return db == 'default'
