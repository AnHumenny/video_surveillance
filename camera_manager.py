import json
import asyncio
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from schemas.repository import Repo
import time


class CameraManager:
    def __init__(self):
        """Initialize the CameraManager with synchronous configuration loading."""
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
        self.background_subtractors = {cam_id: cv2.createBackgroundSubtractorMOG2() for cam_id in self.camera_configs}

    async def initialize(self):
        """Initialize all cameras asynchronously in parallel."""
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
        """Create a cv2.VideoCapture in the thread pool."""
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

            is_open = await loop.run_in_executor(self.executor, check_is_open)
            if not is_open:
                print(f"Камера {cam_id} не открыта после создания.")
                await loop.run_in_executor(self.executor, cap.release)
                return None

            return cap

        except Exception as e:
            print(f"Ошибка при создании VideoCapture для камеры {cam_id}: {e}")
            return None

    async def get_camera(self, cam_id):
        """Retrieve a camera capture asynchronously."""
        if cam_id not in self.cameras:
            print(f"Камера {cam_id} не найдена.")
            return None

        cap = self.cameras[cam_id]
        loop = asyncio.get_running_loop()
        is_open = await loop.run_in_executor(self.executor, cap.isOpened)
        if not is_open:
            print(f"Камера {cam_id} отключена, пытаюсь переподключиться...")
            await loop.run_in_executor(self.executor, cap.release)
            cap = await self._create_capture(cam_id, self.camera_configs[cam_id])
            if cap is None:
                print(f"Не удалось переподключить камеру {cam_id}.")
                return None
            self.cameras[cam_id] = cap
            print(f"Камера {cam_id} переподключена.")
            await asyncio.sleep(1)
        return cap

    async def reinitialize_camera(self, cam_id):
        """Reinitialize a specific camera."""
        if cam_id not in self.camera_configs:
            print(f"Камера {cam_id} не найдена в конфигурации.")
            return False

        if cam_id in self.cameras:
            cap = self.cameras[cam_id]
            loop = asyncio.get_running_loop()
            is_open = await loop.run_in_executor(self.executor, cap.isOpened)
            if is_open:
                print(f"Освобождение камеры {cam_id} перед переинициализацией...")
                await loop.run_in_executor(self.executor, cap.release)
            del self.cameras[cam_id]

        print(f"Переинициализация камеры {cam_id}...")
        cap = await self._create_capture(cam_id, self.camera_configs[cam_id])
        if cap is None:
            print(f"Не удалось переинициализировать камеру {cam_id}.")
            return False

        self.cameras[cam_id] = cap
        print(f"Камера {cam_id} успешно переинициализирована.")

        self.background_subtractors[cam_id] = cv2.createBackgroundSubtractorMOG2()
        return True

    async def get_frame_with_motion_detection(self, cam_id, status_cam):
        """Retrieve a frame from the camera with motion detection and bounding boxes.
        Apply background subtraction to detect moving objects and draw bounding boxes around them.
        Return the processed frame or None if the camera is unavailable or an error occurs.
        """
        cap = await self.get_camera(cam_id)
        if cap is None:
            return None

        loop = asyncio.get_running_loop()

        def read_frame():
            ret, frame = cap.read()
            if not ret:
                return None
            return frame

        frame = await loop.run_in_executor(self.executor, read_frame)
        if frame is None:
            print(f"Не удалось прочитать кадр с камеры {cam_id}.")
            return None

        if not status_cam:
            return frame

        def process_motion_detection(frm, subtractor):
            fg_mask = subtractor.apply(frm)
            kernel = np.ones((5, 5), np.uint8)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            processed_frame = frm.copy()
            for contour in contours:
                if cv2.contourArea(contour) < 500:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(processed_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            return processed_frame

        processed_frame = await loop.run_in_executor(
            self.executor, process_motion_detection, frame, self.background_subtractors[cam_id]
        )

        # elapsed = time.perf_counter() - start_time
        # print(f"[{cam_id}] Frame с детекцией: {elapsed:.4f} сек")

        return processed_frame

    async def cleanup(self):
        """Release camera resources asynchronously."""
        loop = asyncio.get_running_loop()
        for cam_id, cam in self.cameras.items():
            def check_is_open():
                return cam.isOpened()

            is_open = await loop.run_in_executor(self.executor, check_is_open)
            if is_open:
                print(f"Освобождение камеры {cam_id}...")
                def release_camera():
                    cam.release()
                await loop.run_in_executor(self.executor, release_camera)
        self.cameras.clear()
        self.executor.shutdown(wait=True)
        print("Все камеры освобождены.")
