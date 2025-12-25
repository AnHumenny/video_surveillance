import json
import asyncio
import os
from collections import defaultdict
from datetime import datetime
import time
from typing import Dict, Optional, Tuple, Any
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from surveillance.schemas.repository import Repo
from logs.logging_config import logger


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
        self.tracked_objects = {}
        self.next_object_id = 0
        self.count_object = 0
        self.last_video_paths = {}
        self.start_time = datetime.now().replace(microsecond=0)
        self.prev_centroids: Dict[str, list[Tuple[int, int]]] = defaultdict(list)
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
            self,
            cam_id: str,
            save_screenshot: bool = False,
            send_video_tg: bool = False,
            points: Optional[list[tuple[int, int]]] = None,
            reset_counter: bool = False,
    ) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
        """Return the latest frame for a given camera, optionally with motion detection and screenshot saving.

        Args:
            cam_id (str): The ID of the camera.
            save_screenshot (bool): Whether to save a screenshot on central motion detection.
            send_video_tg (bool): Whether to record video for Telegram.
            points: (list of tuple)
            reset_counter: bool
        """
        cam_entry: Optional[Dict[str, Any]] = self.cameras.get(cam_id)
        if not cam_entry:
            logger.error(f"[ERROR] Camera {cam_id} not running")
            return None, None, None

        if reset_counter:
            self.start_time = datetime.now().replace(microsecond=0)
            self.count_object = 0
            logger.info(f"[INFO] Счётчик объектов для камеры {cam_id} сброшен, дата начала изменена")

        queue: asyncio.Queue = cam_entry['queue']
        try:
            frame = await asyncio.wait_for(queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning(f"[WARN] Timeout waiting for frame from camera {cam_id}")
            return None, None, None

        loop = asyncio.get_running_loop()
        subtractor = self.background_subtractors[cam_id]
        screenshot_path = None
        video_path: Optional[str] = None

        def detect(frm: np.ndarray) -> tuple[np.ndarray, Optional[str], bool]:
            """Motion detection with object tracking, screenshot saving, and record trigger."""
            nonlocal screenshot_path

            fg_mask = subtractor.apply(frm)
            kernel = np.ones((5, 5), np.uint8)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
            fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            processed = frm.copy()
            now = time.time()
            last_time = self.last_screenshot_times.get(cam_id, 0)

            zone_x1, zone_x2 = min(p[0] for p in points), max(p[0] for p in points)
            zone_y1, zone_y2 = min(p[1] for p in points), max(p[1] for p in points)

            min_area = 1500
            max_dist = 70
            self.tracked_objects.setdefault(cam_id, {})
            object_data = self.tracked_objects[cam_id]

            should_record = False if not send_video_tg else False   # флаг записи, допилить, видео перестало работать, при включении не работает детекция движения. Скрины заработали корректно

            for cnt in contours:
                if cv2.contourArea(cnt) < min_area:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)
                cx, cy = x + w // 2, y + h // 2
                obj_in_zone = zone_x1 <= cx <= zone_x2 and zone_y1 <= cy <= zone_y2

                matched_id = None
                for obj_id, data in object_data.items():
                    prev_x, prev_y = data["position"]
                    dist = ((prev_x - cx) ** 2 + (prev_y - cy) ** 2) ** 0.5
                    if dist < max_dist and (now - data["last_seen"] < 2):
                        matched_id = obj_id
                        break

                if matched_id is None and obj_in_zone:
                    obj_id = self.next_object_id
                    self.next_object_id += 1
                    object_data[obj_id] = {"position": (cx, cy), "last_seen": now}
                    self.count_object += 1
                    logger.info(f"[INFO] Object with ID={obj_id} in zone. All: {self.count_object}")

                    if save_screenshot and (now - last_time) > 2:
                        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")
                        save_dir = f"media/screenshots/camera_{cam_id}/{timestamp[:10]}/"
                        os.makedirs(save_dir, exist_ok=True)
                        filename = os.path.join(save_dir, f"motion_{timestamp}.jpg")
                        cv2.imwrite(filename, frm)
                        screenshot_path = filename
                        self.last_screenshot_times[cam_id] = now

                    if send_video_tg and not self.recording_flags.get(cam_id, False):
                        should_record = True

                elif matched_id is not None:
                    object_data[matched_id]["position"] = (cx, cy)
                    object_data[matched_id]["last_seen"] = now

                cv2.rectangle(processed, (x, y), (x + w, y + h), (0, 255, 0), 2)

            self.tracked_objects[cam_id] = {
                obj_id: data
                for obj_id, data in object_data.items()
                if now - data["last_seen"] < 2
            }

            cv2.rectangle(processed, (zone_x1, zone_y1), (zone_x2, zone_y2), (0, 0, 255), 2)
            cv2.putText(processed, "Zone", (zone_x1, max(0, zone_y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            if self.recording_flags.get(cam_id):
                cv2.putText(processed, "REC", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            cv2.putText(processed, f"Detected objects: {self.count_object}, started at: {self.start_time}",
                        (points[0][0], 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            return processed, screenshot_path, should_record

        processed, screenshot_path, should_record = await loop.run_in_executor(self.executor, detect, frame)

        if send_video_tg and should_record:
            self.recording_flags[cam_id] = True
            video_path = self.generate_video_path(cam_id)

            async def record_and_reset():
                await self.record_video(cam_id, video_path, duration_sec=int(os.getenv("BOT_SEND_VIDEO")))
                self.recording_flags[cam_id] = False

            asyncio.create_task(record_and_reset())
        else:
            video_path = None

        return processed, screenshot_path, video_path


    @staticmethod
    def generate_video_path(cam_id: str) -> str:
        now = datetime.now()
        filename = f"{cam_id}_{now.strftime('%Y%m%d_%H%M%S')}.mp4"
        current_stamp = now.strftime("%Y-%m-%d")
        save_path = os.path.join("media", "recordings", cam_id, f"camera_{cam_id}_{current_stamp}")
        os.makedirs(save_path, exist_ok=True)
        return os.path.join(save_path, filename)

    async def record_video(self, cam_id: str, full_path: str, duration_sec: int = 5) -> Optional[str]:
        cam_data = self.cameras.get(cam_id)
        if not cam_data:
            logger.error(f"[ERROR] Camera {cam_id} not found")
            return None

        cam_data: Optional[Dict[str, Any]] = self.cameras.get(cam_id)
        queue: asyncio.Queue = cam_data["queue"]

        try:
            frame = await asyncio.wait_for(queue.get(), timeout=int(os.getenv("BOT_SEND_VIDEO")))
        except asyncio.TimeoutError:
            logger.error(f"[ERROR] No camera footage {cam_id}")
            return None

        height, width = frame.shape[:2]
        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        out = cv2.VideoWriter(full_path, fourcc, self.fps, (width, height))

        loop = asyncio.get_running_loop()
        end_time = time.time() + duration_sec


        while time.time() < end_time:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=2)
                await loop.run_in_executor(self.executor, out.write, frame)
            except asyncio.TimeoutError:
                continue

        await loop.run_in_executor(self.executor, out.release)
        logger.info(f"[INFO] Video saved: {full_path}")

        return full_path


    async def _start_camera_reader(self, cam_id: str, url: str, timeout: int) -> None:
        """Start the background reader task for a single camera."""
        cap = await self._safe_create_capture_with_timeout(cam_id, url, timeout)
        if cap is None:
            return

        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
        stop_event = asyncio.Event()
        self.cameras[cam_id] = {"cap": cap, "queue": queue, "stop_event": stop_event}

        async def reader():
            """Camera reading loop with graceful shutdown"""
            loop = asyncio.get_running_loop()
            while not stop_event.is_set():
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

            logger.info(f"[INFO] Camera {cam_id} reader exiting...")

        task = asyncio.create_task(reader(), name=f"reader-{cam_id}")
        self.cameras[cam_id]["task"] = task
        logger.info(f"[INFO] Camera {cam_id} reader started")

    async def _stop_camera_reader(self, cam_id: str) -> None:
        """Stop the reader task and release resources for a specific camera.

        Args:
            cam_id (str): Camera ID.
        """
        logger.debug(f"[DEBUG] Stopping camera reader for {cam_id}")
        cam_entry = self.cameras.get(cam_id)
        if not cam_entry:
            logger.warning(f"[WARNING] No camera entry for {cam_id}")
            return
        task: asyncio.Task = cam_entry.get("task")  # type: ignore
        cap: cv2.VideoCapture = cam_entry.get("cap")  # type: ignore

        if task:
            logger.debug(f"[DEBUG] Cancelling task for camera {cam_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug(f"[DEBUG] Task for camera {cam_id} cancelled")
            except Exception as e:
                logger.error(f"[ERROR] Error cancelling task for {cam_id}: {e}", exc_info=True)
        if cap:
            logger.debug(f"[DEBUG] Releasing VideoCapture for camera {cam_id}")
            try:
                await asyncio.get_running_loop().run_in_executor(self.executor, cap.release)
                logger.info(f"[INFO] Camera {cam_id} reader stopped")
            except Exception as e:
                logger.error(f"[ERROR] Error releasing VideoCapture for {cam_id}: {e}", exc_info=True)
        self.cameras.pop(cam_id, None)
        logger.debug(f"[DEBUG] Camera {cam_id} removed from cameras")


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
            capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not capture.isOpened():
                capture.release()
                return None
            return capture
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
                cap: Optional[cv2.VideoCapture] = cam_data.get("cap")
                ret, frame = cap.read()
                return frame if ret else None
        return None

    async def start_continuous_recording(self, cam_id: str):
        """Starts continuous video recording for 30 seconds until stop command."""
        if self.recording_flags.get(cam_id):
            logger.info(f"[INFO] Recording is already underway for {cam_id}")
            return

        self.recording_flags[cam_id] = True
        logger.info(f"[INFO] Start continuous recording for {cam_id}")

        async def record_loop():
            """Continuous loop of 30s video recordings while flag is True."""
            while self.recording_flags.get(cam_id, False):
                full_path = self.generate_video_path(cam_id)

                cam_entry = self.cameras.get(cam_id)
                if cam_entry and 'current_frame' in cam_entry:
                    frame = cam_entry['current_frame']
                    if frame is not None:
                        cv2.putText(frame, "REC", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

                try:
                    await self.record_video(cam_id, full_path, duration_sec=30)
                except asyncio.CancelledError:
                    logger.info(f"[INFO] Recording cancelled for {cam_id}")
                    break
                except Exception as e:
                    logger.error(f"[ERROR] Failed to record video for {cam_id}: {e}")
                    await asyncio.sleep(5)

            logger.info(f"[INFO] Recording loop exited for {cam_id}")

        task = asyncio.create_task(record_loop(), name=f"recording-{cam_id}")
        self.recording_tasks[cam_id] = task


    async def stop_continuous_recording(self, cam_id: str):
        """Stops the current continuous recording of the camera."""
        if not self.recording_flags.get(cam_id):
            logger.info(f"[INFO] The recording was not made for {cam_id}")
            return

        self.recording_flags[cam_id] = False
        logger.info(f"[INFO] Recording stopped for {cam_id}")

        task = self.recording_tasks.pop(cam_id, None)
        if task is None:
            logger.warning(f"[WARN] No recording task found for {cam_id}")
            return

        if not asyncio.isfuture(task) and not asyncio.iscoroutine(task):
            logger.warning(f"[WARN] Invalid task type for {cam_id}: {type(task)}")
            return

        try:
            await task
            logger.debug(f"[DEBUG] Recording task for {cam_id} completed successfully")
        except asyncio.CancelledError:
            logger.debug(f"[DEBUG] Recording task for {cam_id} was cancelled")
        except Exception as e:
            logger.error(f"[ERROR] Error while stopping recording for {cam_id}: {e}")


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
