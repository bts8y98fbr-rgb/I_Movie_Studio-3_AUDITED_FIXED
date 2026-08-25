class VideoRouter:

    def __init__(
        self,
        providers,
    ):
        self.providers = providers


    def select(
        self,
        model=None,
    ):

        if model:

            for provider in self.providers:

                if provider.name == model:
                    return provider


        if not self.providers:
            raise RuntimeError(
                "No video providers available"
            )


        return self.providers[0]
