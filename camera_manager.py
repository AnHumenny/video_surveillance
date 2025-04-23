import json
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from schemas.repository import Repo


class CameraManager:
    def __init__(self):
        """Инициализация класса (синхронная часть для чтения конфигурации)."""
        camera_config_json = Repo.select_all_cameras_to_json()
        print(f"camera_config_json: {camera_config_json}")
        if not camera_config_json:
            raise ValueError("Конфигурация камер не найдена в базе данных")

        try:
            self.camera_configs = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга конфигурации камер: {e}")

        print("Конфигурация камер:")
        for cam_id, url in self.camera_configs.items():
            print(f"Камера {cam_id}: {url}")

        self.cameras = {}
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def initialize(self):
        """Асинхронная инициализация всех камер параллельно."""
        tasks = [
            self._create_capture(cam_id, url)
            for cam_id, url in self.camera_configs.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (cam_id, _), result in zip(self.camera_configs.items(), results):
            if isinstance(result, Exception):
                print(f"Ошибка инициализации камеры {cam_id}: {result}")
            elif result is None:
                print(f"Не удалось открыть камеру {cam_id}.")
            else:
                print(f"Камера {cam_id} успешно инициализирована.")
                self.cameras[cam_id] = result

    async def _create_capture(self, cam_id, url):
        """Создание cv2.VideoCapture в пуле потоков."""
        loop = asyncio.get_running_loop()
        try:
            def create_video_capture(v_url, api):
                print(f"Попытка открыть камеру {cam_id}: {v_url}")
                capture = cv2.VideoCapture(v_url, api)
                if not capture.isOpened():
                    print(f"cv2.VideoCapture не смог открыть камеру {cam_id}")
                    capture.release()
                    return None
                return capture

            cap = await loop.run_in_executor(self.executor, create_video_capture, url, cv2.CAP_FFMPEG)

            if cap is None:
                return None

            def check_is_open():
                return cap.isOpened()

            is_open = await loop.run_in_executor(self.executor, check_is_open)  # type: ignore
            if not is_open:
                print(f"Камера {cam_id} не открыта после создания.")
                await loop.run_in_executor(self.executor, cap.release)  # type: ignore
                return None

            return cap

        except Exception as e:
            print(f"Ошибка при создании VideoCapture для камеры {cam_id}: {e}")
            return None

    async def get_camera(self, cam_id):
        """Получить данные с камеры асинхронно."""
        if cam_id not in self.cameras:
            print(f"Камера {cam_id} не найдена.")
            return None

        cap = self.cameras[cam_id]
        loop = asyncio.get_running_loop()
        is_open = await loop.run_in_executor(self.executor, cap.isOpened)  # type: ignore
        if not is_open:
            print(f"Камера {cam_id} отключена, пытаюсь переподключиться...")
            await loop.run_in_executor(self.executor, cap.release)  # type: ignore
            cap = await self._create_capture(cam_id, self.camera_configs[cam_id])
            if cap is None:
                print(f"Не удалось переподключить камеру {cam_id}.")
                return None
            self.cameras[cam_id] = cap
            print(f"Камера {cam_id} переподключена.")
            await asyncio.sleep(1)
        return cap

    async def cleanup(self):
        """Асинхронное освобождение ресурсов камер."""
        loop = asyncio.get_running_loop()
        for cam_id, cam in self.cameras.items():
            def check_is_open():
                return cam.isOpened()

            is_open = await loop.run_in_executor(self.executor, check_is_open)  # type: ignore
            if is_open:
                print(f"Освобождение камеры {cam_id}...")
                def release_camera():
                    cam.release()
                await loop.run_in_executor(self.executor, release_camera)  # type: ignore
        self.cameras.clear()
        self.executor.shutdown(wait=True)
        print("Все камеры освобождены.")
