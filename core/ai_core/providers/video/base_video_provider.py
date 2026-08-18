from abc import ABC, abstractmethod


class BaseVideoProvider(ABC):

    def __init__(self, name):

        self.name = name


    @abstractmethod
    def submit_generation(
        self,
        prompt,
        quality,
        metadata=None,
    ):
        pass


    @abstractmethod
    def get_status(
        self,
        job_id,
    ):
        pass
