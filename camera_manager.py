import json
import asyncio
import logging
import os
from datetime import datetime
import time
from typing import Dict, Optional, Tuple
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from numpy import ndarray
from schemas.repository import Repo

logger = logging.getLogger(__name__)

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
        self.recording_flags = {}
        self.recording_tasks = {}
        self.last_screenshot_times = {}
        if not camera_config_json:
            raise ValueError("Camera configuration not found in database")

        try:
            self.camera_configs: Dict[str, str] = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing camera configuration: {e}")

        logger.info("Camera configuration:")
        for cam_id, url in self.camera_configs.items():
            logger.info(f"  Camera {cam_id}: {url}")

        self.fps = fps
        self.frame_period = 1.0 / fps
        self.max_queue_size = max_queue_size
        self.executor = ThreadPoolExecutor(max_workers=4)
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
            logger.info("[WARN] Camera configuration not found in database.")
            return False

        try:
            new_configs = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            logger.info(f"Error parsing camera configuration: {e}")
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


    async def get_frame_without_motion_detection(self, cam_id: str) -> Optional[np.ndarray]:
        """Return the latest frame for a given camera without any processing.

        Args:
            cam_id (str): The ID of the camera.

        Returns:
            Optional[np.ndarray]: Latest frame or None if unavailable.
        """
        cam_entry = self.cameras.get(cam_id)
        if not cam_entry:
            logger.error(f"[ERROR] Camera {cam_id} not running")
            return None

        queue: asyncio.Queue = cam_entry['queue']  # type: ignore
        try:
            frame = await asyncio.wait_for(queue.get(), timeout=2.0)
            return frame
        except asyncio.TimeoutError:
            logger.warning(f"[WARN] Timeout waiting for frame from camera {cam_id}")
            return None


    async def get_frame_with_motion_detection(
            self, cam_id: str, enable_motion: bool, save_screenshot: bool = False
    ) -> Tuple[Optional[np.ndarray], Optional[str]]:
        """Return the latest frame for a given camera, optionally with motion detection and screenshot saving.

        Args:
            cam_id (str): The ID of the camera.
            enable_motion (bool): Whether to apply motion detection.
            save_screenshot (bool): Whether to save a screenshot on central motion detection.

        Returns:
            Optional[np.ndarray]: Latest processed frame or None if unavailable.
        """
        cam_entry = self.cameras.get(cam_id)
        if not cam_entry:
            logger.error(f"[ERROR] Camera {cam_id} not running")
            return None, None

        queue: asyncio.Queue = cam_entry['queue']  # type: ignore
        try:
            frame = await asyncio.wait_for(queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning(f"[WARN] Timeout waiting for frame from camera {cam_id}")
            return None, None

        if not enable_motion:
            return frame

        loop = asyncio.get_running_loop()
        subtractor = self.background_subtractors[cam_id]
        screenshot_path = None

        def detect(frm: np.ndarray) -> tuple[ndarray, str | None]:
            """Motion detection, optionally with screenshot saving."""
            nonlocal screenshot_path
            fg_mask = subtractor.apply(frm)
            kernel = np.ones((5, 5), np.uint8)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            height, width = frm.shape[:2]
            center_x, center_y = width // 2, height // 2
            margin_x = width // 6
            margin_y = height // 6

            processed = frm.copy()
            screenshot_taken = False

            now = time.time()
            last_time = self.last_screenshot_times.get(cam_id, 0)

            for cnt in contours:
                if cv2.contourArea(cnt) < 500:
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                cx, cy = x + w // 2, y + h // 2
                # пока пилим в центр, допилить детекцию по координатам, актуально для Akyvox
                if (
                        save_screenshot and
                        (center_x - margin_x <= cx <= center_x + margin_x) and
                        (center_y - margin_y <= cy <= center_y + margin_y) and
                        not screenshot_taken and
                        (now - last_time) > 5
                ):
                    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
                    save_dir = f"screenshots/camera_{cam_id}/{timestamp[:10]}/"
                    os.makedirs(save_dir, exist_ok=True)
                    filename = os.path.join(save_dir, f"motion_{timestamp}.jpg")
                    cv2.imwrite(filename, frm)
                    screenshot_path = filename
                    logger.info(f"[INFO] Motion detected. Saved: {filename}")
                    self.last_screenshot_times[cam_id] = now
                    screenshot_taken = True

                cv2.rectangle(processed, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if self.recording_flags.get(cam_id, False):
                cv2.rectangle(processed, (10, 10), (150, 60), (0, 0, 255), -1)
                cv2.putText(processed, "REC", (20, 45), cv2.FONT_HERSHEY_SIMPLEX,
                            1.2, (255, 255, 255), 2)

            return processed, screenshot_path

        return await loop.run_in_executor(self.executor, detect, frame)

    async def cleanup(self) -> None:
        """Stop all camera readers and release resources."""
        for cam_id in list(self.cameras.keys()):
            await self._stop_camera_reader(cam_id)
        self.executor.shutdown(wait=True)
        logger.info("All cameras cleaned up.")

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
                    logger.warning(f"[WARN] Empty frame from {cam_id}, trying reconnect")
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
        logger.info(f"[INFO] Camera {cam_id} reader started")

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
        logger.info(f"[INFO] Camera {cam_id} reader stopped")
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
            logger.error(f"[ERROR] Timeout connecting to camera {cam_id}")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Exception connecting to camera {cam_id}: {e}")
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
            logger.info(f"[INFO] Opening camera {cam_id}: {url}")
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                cap.release()
                return None
            return cap
        cap = await loop.run_in_executor(self.executor, open_cap)
        if cap is None:
            logger.error(f"[ERROR] cv2.VideoCapture failed for {cam_id}")
        return cap

    async def get_current_frame(self, cam_id):
        """make current screenshot"""
        cam_data = self.cameras.get(cam_id)
        if cam_data:
            cap = cam_data.get("cap")
            if cap:
                ret, frame = cap.read()
                return frame if ret else None
        return None

    async def start_continuous_recording(self, cam_id: str):
        """Starts continuous video recording for 30 seconds until stop command."""
        if cam_id in self.recording_flags and self.recording_flags[cam_id]:
            logger.info(f"[INFO] Registration is already underway for {cam_id}")
            return
        self.recording_flags[cam_id] = True
        logger.info(f"[INFO] Start continuous recording for {cam_id}")

        async def record_loop():
            """
            Starts a looped (continuous) video recording in 30 second blocks.

            Recording continues until a stop command is received.
            Each fragment is saved separately. Uses the self.recording_flags[cam_id] flag
            to control start/stop.
            """
            while self.recording_flags.get(cam_id, False):
                await self.record_video(cam_id, duration_sec=30)
        task = asyncio.create_task(record_loop(), name=f"recording-{cam_id}")
        self.recording_tasks[cam_id] = task


    async def stop_continuous_recording(self, cam_id: str):
        """Stops the current continuous recording of the camera."""
        if self.recording_flags.get(cam_id):
            self.recording_flags[cam_id] = False
            logger.info(f"[INFO] Recording stopped for {cam_id}")
            task = self.recording_tasks.pop(cam_id, None)
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        else:
            logger.info(f"[INFO] The recording was not made for {cam_id}")

    async def record_video(self, cam_id: str, duration_sec: int = 10) -> Optional[str]:
        """Records video from the camera for the specified time (in seconds)."""
        cam_data = self.cameras.get(cam_id)
        if not cam_data:
            logger.error(f"[ERROR] Camera {cam_id} not found")
            return None
        queue: asyncio.Queue = cam_data["queue"]
        now = datetime.now()
        filename = f"{cam_id}_{now.strftime('%Y%m%d_%H%M%S')}.avi"
        current_stamp = now.strftime("%Y-%m-%d")
        save_path = os.path.join("recordings", cam_id, f"camera_{cam_id}_{current_stamp}")
        os.makedirs(save_path, exist_ok=True)
        full_path = os.path.join(save_path, filename)
        logger.info(f"[INFO] Record video started. Saved: {filename}")

        try:
            frame = await asyncio.wait_for(queue.get(), timeout=5)
        except asyncio.TimeoutError:
            logger.error(f"[ERROR] No camera footage {cam_id}")
            return None

        height, width = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(full_path, fourcc, self.fps, (width, height))

        loop = asyncio.get_running_loop()

        async def writer():
            """
            Asynchronous task of recording a fixed-duration video clip.

            Reads frames from the queue and writes them to a file using cv2.VideoWriter`.
            The recording continues for `duration_sec` seconds, taking into account the time.
            All write and release operations of the `out` resource are performed in the `ThreadPoolExecutor`,
            to avoid blocking the main asynchronous thread.

            """
            end_time = time.time() + duration_sec
            while time.time() < end_time:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=2)
                    await loop.run_in_executor(self.executor, out.write, frame)
                except asyncio.TimeoutError:
                    continue
            await loop.run_in_executor(self.executor, out.release)

        await writer()
        logger.info(f"[INFO] Video saved: {full_path}")
        return full_path


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
            logger.warning(f"[WARN] No configuration found for camera {cam_id}")
            return False
        try:
            single_config = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing camera configuration: {e}")

        if cam_id not in single_config:
            logger.info(f"[INFO] Camera {cam_id} disabled or missing in DB. Removing from runtime.")
            await self._stop_camera_reader(cam_id)
            self.camera_configs.pop(cam_id, None)
            self.background_subtractors.pop(cam_id, None)
            return False

        if cam_id in self.cameras:
            logger.info(f"[INFO] Stopping camera {cam_id} before reinitialization...")
            await self._stop_camera_reader(cam_id)

        self.camera_configs[cam_id] = single_config[cam_id]
        self.background_subtractors[cam_id] = cv2.createBackgroundSubtractorMOG2()

        logger.info(f"[INFO] Reinitializing camera {cam_id}...")
        await self._start_camera_reader(cam_id, self.camera_configs[cam_id], timeout=5)
        logger.info(f"[INFO] Camera {cam_id} successfully reinitialized.")
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
            logger.info(f"[INFO] Reconnect {cam_id}: attempt {attempt}/{attempts}")
            cap = await self._create_capture(cam_id, url)
            if cap:
                await asyncio.get_running_loop().run_in_executor(self.executor, self.cameras[cam_id]['cap'].release)
                self.cameras[cam_id]['cap'] = cap
                logger.info(f"[INFO] Camera {cam_id} reconnected")
                return True
            await asyncio.sleep(delay)
        logger.error(f"[ERROR] Cannot reconnect camera {cam_id}")
        return False
