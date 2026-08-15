from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import json
import uuid


class VideoProvider(ABC):


    @abstractmethod
    def generate(
        self,
        prompt,
        quality,
        metadata=None
    ):
        pass



class MockVideoProvider(VideoProvider):


    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )


        self.asset_path = (
            self.project_path /
            "assets" /
            "video_generated"
        )


        self.asset_path.mkdir(
            parents=True,
            exist_ok=True
        )



    def generate(
        self,
        prompt,
        quality,
        metadata=None
    ):


        asset_id = str(
            uuid.uuid4()
        )[:8]


        result = {

            "asset_id":
                asset_id,

            "type":
                "video",


            "provider":
                "mock",


            "prompt":
                prompt,


            "quality":
                quality,


            "status":
                "generated",


            "created":
                datetime.now().isoformat(),


            "metadata":
                metadata or {},


            "file":
                None

        }



        file_path = (
            self.asset_path /
            f"{asset_id}.json"
        )


        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
                ensure_ascii=False
            )


        result["asset_file"] = str(
            file_path
        )


        return result



class VideoProviderManager:


    def __init__(
        self,
        project_path,
        provider="mock"
    ):


        if provider == "mock":

            self.provider = MockVideoProvider(
                project_path
            )

        else:

            raise ValueError(
                "Unknown video provider"
            )



    def generate_video(
        self,
        prompt,
        quality,
        metadata=None
    ):

        return self.provider.generate(
            prompt,
            quality,
            metadata
        )
