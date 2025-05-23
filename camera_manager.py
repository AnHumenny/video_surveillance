import json
import asyncio
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from schemas.repository import Repo


class CameraManager:
    def __init__(self):
        """Initialization of basic structures without loading camera configuration."""
        camera_config_json = Repo.select_all_cameras_to_json()
        if not camera_config_json:
            raise ValueError("Camera configuration not found in database")

        try:
            self.camera_configs = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing camera configuration: {e}")

        print("Camera configuration:")
        for cam_id, url in self.camera_configs.items():
            print(f"Камера {cam_id}: {url}")

        self.cameras = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.background_subtractors = {cam_id: cv2.createBackgroundSubtractorMOG2() for cam_id in self.camera_configs}

    async def load_camera_configs(self):
        """Asynchronous loading of camera configuration from the database."""
        camera_config_json = Repo.select_all_cameras_to_json()
        if not camera_config_json:
            print("Camera configuration not found in database.")
            return False

        try:
            self.camera_configs = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing camera configuration: {e}")
            return False

        print("Camera configuration loaded:")
        for cam_id, url in self.camera_configs.items():
            if "stimeout" not in url:
                self.camera_configs[cam_id] += "?stimeout=20000000"
            print(f"  Camera {cam_id}: {url}")

        self.background_subtractors = {
            cam_id: cv2.createBackgroundSubtractorMOG2()
            for cam_id in self.camera_configs
        }

        return True

    async def initialize(self, timeout_per_camera=5):
        """Initialize all cameras with connection timeout."""
        tasks = [
            self._safe_create_capture_with_timeout(cam_id, url, timeout_per_camera)
            for cam_id, url in self.camera_configs.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (cam_id, _), result in zip(self.camera_configs.items(), results):
            if isinstance(result, Exception):
                print(f"Error initializing camera {cam_id}: {result}")
            elif result is None:
                print(f"Camera {cam_id} not initializing.")
            else:
                print(f"Camera {cam_id} initialized successfully.")
                self.cameras[cam_id] = result

    async def _safe_create_capture_with_timeout(self, cam_id, url, timeout):
        """Create a Time-Limited Camera Capture."""
        try:
            return await asyncio.wait_for(self._create_capture(cam_id, url), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"Timeout connecting to camera {cam_id} ({timeout} second)")
            return None
        except Exception as e:
            print(f"Exception when connecting to camera {cam_id}: {e}")
            return None


    async def _create_capture(self, cam_id, url):
        """Create cv2.VideoCapture in thread pool."""
        loop = asyncio.get_running_loop()

        def create_video_capture(v_url, api):
            print(f"Trying to open the camera {cam_id}: {v_url}")
            capture = cv2.VideoCapture(v_url, api)
            if not capture.isOpened():
                print(f"cv2.VideoCapture cannot open the camera {cam_id}")
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
            print(f"Camera {cam_id} not opened after creation.")
            await loop.run_in_executor(self.executor, cap.release)
            return None

        return cap


    async def get_camera(self, cam_id):
        """Retrieve a camera capture asynchronously."""
        if cam_id not in self.cameras:
            print(f"Camera {cam_id} not found.")
            return None

        cap = self.cameras[cam_id]
        loop = asyncio.get_running_loop()
        is_open = await loop.run_in_executor(self.executor, cap.isOpened)
        if not is_open:
            print(f"Camera {cam_id} disconnected, trying to reconnect...")
            await loop.run_in_executor(self.executor, cap.release)
            cap = await self._create_capture(cam_id, self.camera_configs[cam_id])
            if cap is None:
                print(f"Failed to reconnect camera {cam_id}.")
                return None
            self.cameras[cam_id] = cap
            print(f"Camera {cam_id} reconnect.")
            await asyncio.sleep(1)
        return cap

    async def reinitialize_camera(self, cam_id):
        """Reinitialize a specific camera if it is active."""
        camera_config_json = Repo.reinit_camera(cam_id)

        if not camera_config_json:
            return None

        try:
            single_config = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing camera configuration: {e}")

        if cam_id not in single_config:
            print(f"Camera {cam_id} disabled or not found in configuration. Removed...")
            if cam_id in self.cameras:
                cap = self.cameras[cam_id]
                loop = asyncio.get_running_loop()
                is_open = await loop.run_in_executor(self.executor, cap.isOpened)
                if is_open:
                    await loop.run_in_executor(self.executor, cap.release)
                del self.cameras[cam_id]
            if cam_id in self.background_subtractors:
                del self.background_subtractors[cam_id]
            if cam_id in self.camera_configs:
                del self.camera_configs[cam_id]
            return False

        self.camera_configs[cam_id] = single_config[cam_id]

        if cam_id in self.cameras:
            cap = self.cameras[cam_id]
            loop = asyncio.get_running_loop()
            is_open = await loop.run_in_executor(self.executor, cap.isOpened)
            if is_open:
                print(f"Freeing the camera {cam_id} before reinitialization...")
                await loop.run_in_executor(self.executor, cap.release)
            del self.cameras[cam_id]

        print(f"Reinitializing the camera{cam_id}...")
        cap = await self._create_capture(cam_id, self.camera_configs[cam_id])
        if cap is None:
            print(f"Failed to reinitialize camera {cam_id}.")
            return False

        self.cameras[cam_id] = cap
        self.background_subtractors[cam_id] = cv2.createBackgroundSubtractorMOG2()
        print(f"Camera {cam_id} successfully reinitialized.")
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
            print(f"Failed to read frame from camera {cam_id}.")
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
        return processed_frame

    async def cleanup(self):
        """Release camera resources asynchronously."""
        loop = asyncio.get_running_loop()
        for cam_id, cam in self.cameras.items():
            def check_is_open():
                return cam.isOpened()

            is_open = await loop.run_in_executor(self.executor, check_is_open)
            if is_open:
                print(f"Freeing the camera {cam_id}...")
                def release_camera():
                    cam.release()
                await loop.run_in_executor(self.executor, release_camera)
        self.cameras.clear()
        self.executor.shutdown(wait=True)
        print("All cells are released.")
