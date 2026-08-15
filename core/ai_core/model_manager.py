class ModelManager:

    def __init__(self):
        self.models = {}


    def register_model(self, category, model_name):
        if category not in self.models:
            self.models[category] = []

        self.models[category].append(model_name)


    def get_models(self, category):
        return self.models.get(category, [])


    def list_models(self):
        return self.models
