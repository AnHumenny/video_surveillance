import ffmpeg
import numpy as np
import cv2
from logs.logging_config import logger
import subprocess
import json

rtsp_url = "rtsp://user:password@192.168.1.34"

coordinate = []
should_exit = False

def get_video_params(rtsp_url):
    """Getting the width, height of the object of the requested camera"""
    cmd = [
        'ffprobe',
        '-rtsp_transport', 'tcp',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        rtsp_url
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        logger.error("[ERROR] :", result.stderr)
        return None

    data = json.loads(result.stdout)

    try:
        stream_info = data["streams"][0]
        width_frame = stream_info.get("width")
        height_frame = stream_info.get("height")
        return {
            "width": width_frame,
            "height": height_frame,
        }
    except (IndexError, KeyError):
        print("Не удалось извлечь параметры.")
        return None

params = get_video_params(rtsp_url)
if not params:
    logger.info("Не получилось подключится к камере, выход")
    exit()
width, height = params.get("width"), params.get("height")
frame_size = width * height * 3
logger.info(f"[INFO width = {width}, height = {height}")

def mouse_callback(event, x, y, flags, param):
    """mouse click on coordinate points"""
    global should_exit
    try:
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(coordinate) < 4:
                coordinate.append((x, y))
                logger.info(f"Click! x: {x}, y: {y}")
                if len(coordinate) == 4:
                    logger.info("Get 4 coordinates, waiting for 5th click to finish...")
            elif len(coordinate) == 4:
                logger.info("Fifth click, stopping...")
                should_exit = True
    except Exception as e:
        logger.error(f"Error in mouse_callback: {e}")


def draw_overlay(frame, points):
    """Drawing coordinates by points"""
    try:
        valid_points = []
        for pt in points:
            try:
                if isinstance(pt, tuple) and len(pt) == 2:
                    x, y = int(pt[0]), int(pt[1])
                    if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]:
                        valid_points.append((x, y))
                    else:
                        logger.warning(f"Out-of-frame coordinate: ({x}, {y})")
                else:
                    logger.warning(f"Incorrect point format: {pt}")
            except Exception as e:
                logger.error(f"Point processing error {pt}: {e}")

        for i in range(1, len(valid_points)):
            cv2.line(frame, valid_points[i - 1], valid_points[i], (0, 255, 0), 2)

        if len(valid_points) == 4:
            cv2.line(frame, valid_points[3], valid_points[0], (0, 255, 0), 2)

        for pt in valid_points:
            cv2.circle(frame, pt, 5, (0, 0, 255), -1)

    except Exception as e:
        logger.error(f"Error in draw_overlay: {e}")

def get_coordinates_from_rtsp():
    """getting coordinates from rtsp"""
    global should_exit
    should_exit = False

    try:
        logger.info("Initializing FFmpeg...")
        process = (
            ffmpeg
            .input(rtsp_url, rtsp_transport='tcp')
            .output('pipe:', format='rawvideo', pix_fmt='bgr24')
            .run_async(pipe_stdout=True)
        )
    except Exception as e:
        logger.error(f"Error initializing FFmpeg: {e}")
        return []

    try:
        logger.info("Creating OpenCV window...")
        cv2.namedWindow("frame")
        cv2.setMouseCallback("frame", mouse_callback)
    except Exception as e:
        logger.error(f"Error creating OpenCV window: {e}")
        return []

    try:
        while cv2.getWindowProperty("frame", cv2.WND_PROP_VISIBLE) > 0 and not should_exit:
            try:
                in_bytes = process.stdout.read(frame_size)
                if len(in_bytes) != frame_size:
                    logger.warning("Incorrect frame size, skipping...")
                    continue

                frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])
                frame = frame.copy()

                draw_overlay(frame, coordinate)

                cv2.imshow("frame", frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("Key 'q' pressed, stopping...")
                    break


            except Exception as e:
                logger.error(f"Error in frame processing: {e}")
                break

    finally:
        logger.info("Closing resources...")
        process.stdout.close()
        process.wait()
        cv2.destroyAllWindows()
        return coordinate


if __name__ == "__main__":
    coords = get_coordinates_from_rtsp()
    logger.info(f"Result Coordinates: {coords}")  # в control?
