import json
import asyncio
from typing import Dict, Optional
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from schemas.repository import Repo


class CameraManager:
    """Asynchronous manager that maintains exactly **one** VideoCapture per physical
    camera, runs a background reader task for each camera, and exposes the most
    recent frame to any number of clients via an asyncio.Queue.  This prevents
    concurrent access to the same FFmpeg/avcodec context and eliminates the
    `async_lock` assertion you were hitting.
    """

    def __init__(self, max_queue_size: int = 10, fps: float = 30.0):
        """Initialize CameraManager by loading configs and setting up runtime structures."""
        camera_config_json = Repo.select_all_cameras_to_json()
        if not camera_config_json:
            raise ValueError("Camera configuration not found in database")

        try:
            self.camera_configs: Dict[str, str] = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing camera configuration: {e}")

        print("Camera configuration:")
        for cam_id, url in self.camera_configs.items():
            print(f"  Camera {cam_id}: {url}")

        self.fps = fps
        self.frame_period = 1.0 / fps
        self.max_queue_size = max_queue_size
        self.executor = ThreadPoolExecutor(max_workers=4)
        # cam_id -> {cap, queue, task}
        self.cameras: Dict[str, Dict[str, object]] = {}
        self.background_subtractors = {
            cam_id: cv2.createBackgroundSubtractorMOG2() for cam_id in self.camera_configs
        }


    async def initialize(self, timeout_per_camera: int = 5) -> None:
        """Start background reader for every camera found in DB.

        Args:
            timeout_per_camera (int): Timeout in seconds for each camera connection.
        """
        tasks = [self._start_camera_reader(cam_id, url, timeout_per_camera)
                 for cam_id, url in self.camera_configs.items()]
        await asyncio.gather(*tasks)

    async def load_camera_configs(self) -> bool:
        """Reload camera configs from DB, start new readers and stop removed ones.

        Returns:
            bool: True if configs reloaded successfully, False on error.
        """
        camera_config_json = Repo.select_all_cameras_to_json()
        if not camera_config_json:
            print("[WARN] Camera configuration not found in database.")
            return False

        try:
            new_configs = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing camera configuration: {e}")
            return False

        for cam_id, url in new_configs.items():
            if cam_id not in self.camera_configs:
                self.camera_configs[cam_id] = url
                self.background_subtractors[cam_id] = cv2.createBackgroundSubtractorMOG2()
                await self._start_camera_reader(cam_id, url, timeout=5)

        for cam_id in list(self.camera_configs.keys()):
            if cam_id not in new_configs:
                await self._stop_camera_reader(cam_id)
                del self.camera_configs[cam_id]
                self.background_subtractors.pop(cam_id, None)

        return True

    async def get_frame_with_motion_detection(self, cam_id: str, enable_motion: bool) -> Optional[np.ndarray]:
        """Return the latest frame for a given camera, optionally with motion detection.

        Args:
            cam_id (str): The ID of the camera.
            enable_motion (bool): Whether to apply motion detection.

        Returns:
            Optional[np.ndarray]: Latest processed frame or None if unavailable.
        """
        cam_entry = self.cameras.get(cam_id)
        if not cam_entry:
            print(f"[ERROR] Camera {cam_id} not running")
            return None

        queue: asyncio.Queue = cam_entry['queue']  # type: ignore
        try:
            frame = await asyncio.wait_for(queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            print(f"[WARN] Timeout waiting for frame from camera {cam_id}")
            return None

        if not enable_motion:
            return frame

        loop = asyncio.get_running_loop()
        subtractor = self.background_subtractors[cam_id]

        def detect(frm: np.ndarray) -> np.ndarray:
            """Motion detection"""
            fg_mask = subtractor.apply(frm)
            kernel = np.ones((5, 5), np.uint8)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            processed = frm.copy()
            for cnt in contours:
                if cv2.contourArea(cnt) < 500:
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(processed, (x, y), (x + w, y + h), (0, 255, 0), 2)
            return processed

        return await loop.run_in_executor(self.executor, detect, frame)

    async def cleanup(self) -> None:
        """Stop all camera readers and release resources."""
        for cam_id in list(self.cameras.keys()):
            await self._stop_camera_reader(cam_id)
        self.executor.shutdown(wait=True)
        print("All cameras cleaned up.")

    async def _start_camera_reader(self, cam_id: str, url: str, timeout: int) -> None:
        """Start the background reader task for a single camera.

        Args:
            cam_id (str): Camera ID.
            url (str): Camera RTSP or HTTP stream URL.
            timeout (int): Timeout for initial connection.
        """
        cap = await self._safe_create_capture_with_timeout(cam_id, url, timeout)
        if cap is None:
            return

        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.cameras[cam_id] = {"cap": cap, "queue": queue}

        async def reader():
            """Creating and initializing cv2.VideoCapture with timeout"""
            loop = asyncio.get_running_loop()
            while True:
                def read():
                    ret, frm = cap.read()
                    return frm if ret else None

                frame = await loop.run_in_executor(self.executor, read)
                if frame is None:
                    print(f"[WARN] Empty frame from {cam_id}, trying reconnect")
                    ok = await self._try_reconnect(cam_id)
                    if not ok:
                        await asyncio.sleep(1)
                    continue

                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                await queue.put(frame)
                await asyncio.sleep(self.frame_period)

        task = asyncio.create_task(reader(), name=f"reader-{cam_id}")
        self.cameras[cam_id]["task"] = task
        print(f"[INFO] Camera {cam_id} reader started")

    async def _stop_camera_reader(self, cam_id: str) -> None:
        """Stop the reader task and release resources for a specific camera.

        Args:
            cam_id (str): Camera ID.
        """
        cam_entry = self.cameras.get(cam_id)
        if not cam_entry:
            return
        task: asyncio.Task = cam_entry.get("task")  # type: ignore
        cap: cv2.VideoCapture = cam_entry.get("cap")  # type: ignore

        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if cap:
            await asyncio.get_running_loop().run_in_executor(self.executor, cap.release)
        print(f"[INFO] Camera {cam_id} reader stopped")
        self.cameras.pop(cam_id, None)

    async def _safe_create_capture_with_timeout(self, cam_id: str, url: str, timeout: int):
        """Create cv2.VideoCapture with timeout and error handling.

        Args:
            cam_id (str): Camera ID.
             url (str): Stream URL.
            timeout (int): Timeout in seconds.

            Returns:
            Optional[cv2.VideoCapture]: Opened capture or None.
        """
        try:
            return await asyncio.wait_for(self._create_capture(cam_id, url), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"[ERROR] Timeout connecting to camera {cam_id}")
            return None
        except Exception as e:
            print(f"[ERROR] Exception connecting to camera {cam_id}: {e}")
            return None

    async def _create_capture(self, cam_id: str, url: str):
        """Create cv2.VideoCapture in thread executor.

        Args:
            cam_id (str): Camera ID.
            url (str): Stream URL.

        Returns:
            Optional[cv2.VideoCapture]: Opened capture or None.
        """
        loop = asyncio.get_running_loop()

        def open_cap():
            print(f"[INFO] Opening camera {cam_id}: {url}")
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                return None
            return cap

        cap = await loop.run_in_executor(self.executor, open_cap)
        if cap is None:
            print(f"[ERROR] cv2.VideoCapture failed for {cam_id}")
        return cap

    async def reinitialize_camera(self, cam_id: str) -> bool:
        """
        Reinitialize a specific camera if it is active in the database.

        This stops the existing reader, removes old configs, fetches the new config,
        and starts a new reader with updated parameters.

        Returns:
            True if the camera was successfully reinitialized, False otherwise.
        """
        camera_config_json = Repo.reinit_camera(cam_id)
        if not camera_config_json:
            print(f"[WARN] No configuration found for camera {cam_id}")
            return False

        try:
            single_config = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing camera configuration: {e}")

        if cam_id not in single_config:
            print(f"[INFO] Camera {cam_id} disabled or missing in DB. Removing from runtime.")
            await self._stop_camera_reader(cam_id)
            self.camera_configs.pop(cam_id, None)
            self.background_subtractors.pop(cam_id, None)
            return False

        if cam_id in self.cameras:
            print(f"[INFO] Stopping camera {cam_id} before reinitialization...")
            await self._stop_camera_reader(cam_id)

        self.camera_configs[cam_id] = single_config[cam_id]
        self.background_subtractors[cam_id] = cv2.createBackgroundSubtractorMOG2()

        print(f"[INFO] Reinitializing camera {cam_id}...")
        await self._start_camera_reader(cam_id, self.camera_configs[cam_id], timeout=5)
        print(f"[INFO] Camera {cam_id} successfully reinitialized.")
        return True

    async def _try_reconnect(self, cam_id: str, attempts: int = 3, delay: float = 2.0) -> bool:
        """Attempt to reconnect to a camera up to `attempts` times.

        Args:
            cam_id (str): Camera ID.
            attempts (int): Number of reconnect attempts.
            delay (float): Delay in seconds between attempts.

        Returns:
            bool: True if reconnection succeeded, False otherwise.
        """
        url = self.camera_configs.get(cam_id)
        if not url:
            return False

        for attempt in range(1, attempts + 1):
            print(f"[INFO] Reconnect {cam_id}: attempt {attempt}/{attempts}")
            cap = await self._create_capture(cam_id, url)
            if cap:
                # replace cap in entry
                await asyncio.get_running_loop().run_in_executor(self.executor, self.cameras[cam_id]['cap'].release)
                self.cameras[cam_id]['cap'] = cap
                print(f"[INFO] Camera {cam_id} reconnected")
                return True
            await asyncio.sleep(delay)
        print(f"[ERROR] Cannot reconnect camera {cam_id}")
        return False
