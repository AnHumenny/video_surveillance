import os
import shutil
from datetime import datetime, timedelta
from celery_task.path_utils import get_absolute_recordings_path, get_absolute_logs_path
from surveillance.schemas.repository import logger


def delete_old_log_files(days_threshold=7):
    """Celery task to delete old log files from logs directory.

    This task removes log folders (in YYYY-MM-DD format) older than
    the specified threshold from the main logs directory.

    Args:
        days_threshold (int, optional): Number of days to keep log files.
            Folders older than this threshold will be deleted. Defaults to 30.

    Returns:
        dict: Detailed results of the cleanup operation including:
            - success (bool): Whether operation completed without errors
            - threshold_date (str): Date threshold in 'YYYY-MM-DD' format
            - days_threshold (int): Days threshold used
            - logs_path (str): Path to logs directory
            - deleted_folders (List[dict]): Details of deleted folders
            - deleted_count (int): Number of folders deleted
            - errors (List[str]): Error messages encountered
            - error_count (int): Number of errors
            - timestamp (str): ISO timestamp of completion
    """

    logger.info("=" * 50)
    logger.info(f"НАЧАЛО ОЧИСТКИ ЛОГОВ. Порог: {days_threshold} дней")

    logs_path = get_absolute_logs_path()
    logger.info(f"Путь к логам: {logs_path}")

    if not os.path.exists(logs_path):
        error_msg = f"Папка logs не существует: {logs_path}"
        logger.error(error_msg)
        return {
            'success': False,
            'threshold_date': '',
            'days_threshold': days_threshold,
            'logs_path': logs_path,
            'deleted_folders': [],
            'deleted_count': 0,
            'errors': [error_msg],
            'error_count': 1,
            'timestamp': datetime.now().isoformat()
        }

    threshold_date = datetime.now() - timedelta(days=days_threshold)
    logger.info(f"Пороговая дата: {threshold_date.strftime('%Y-%m-%d')}")

    deleted_folders = []
    errors = []

    try:
        items = os.listdir(logs_path)
        logger.info(f"Найдено элементов в logs: {len(items)}")

        for folder_name in items:
            folder_path = os.path.join(logs_path, folder_name)

            if not os.path.isdir(folder_path):
                logger.debug(f"ПРОПУСКАЕМ файл: {folder_name}")
                continue

            try:
                folder_date = datetime.strptime(folder_name, '%Y-%m-%d')

                if folder_date < threshold_date:
                    logger.info(f"  УДАЛЯЕМ лог-папку: {folder_name} (дата: {folder_date.date()})")

                    try:
                        shutil.rmtree(folder_path)

                        deleted_folders.append({
                            'folder_name': folder_name,
                            'folder_date': folder_date.strftime('%Y-%m-%d'),
                            'path': folder_path,
                        })

                        logger.info(f"Лог-папка удалена: {folder_name}")

                    except PermissionError as e:
                        error_msg = f"Нет прав для удаления {folder_path}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                    except Exception as e:
                        error_msg = f"Ошибка при удалении {folder_path}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                else:
                    logger.debug(f"ОСТАВЛЯЕМ лог-папку: {folder_name} "
                                 f"(дата: {folder_date.date()}, еще актуальна)")

            except ValueError:
                logger.debug(f"ПРОПУСКАЕМ папку: {folder_name} (не формат даты YYYY-MM-DD)")
                continue

    except PermissionError as e:
        error_msg = f"Нет доступа к папке logs: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    except Exception as e:
        error_msg = f"Ошибка при чтении папки logs: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    result = {
        'success': len(errors) == 0,
        'threshold_date': threshold_date.strftime('%Y-%m-%d'),
        'days_threshold': days_threshold,
        'logs_path': logs_path,
        'deleted_folders': deleted_folders,
        'deleted_count': len(deleted_folders),
        'errors': errors,
        'error_count': len(errors),
        'timestamp': datetime.now().isoformat(),
        'total_space_freed_mb': sum(folder.get('size_mb', 0) for folder in deleted_folders)
    }

    logger.info("\n" + "=" * 50)
    logger.info("ИТОГИ ОЧИСТКИ ЛОГОВ:")
    logger.info(f"Путь к логам: {logs_path}")
    logger.info(f"Пороговая дата: {threshold_date.strftime('%Y-%m-%d')}")
    logger.info(f"Удалено папок: {len(deleted_folders)}")
    logger.info(f"Ошибок: {len(errors)}")

    if errors:
        logger.warning("Ошибки:")
        for error in errors:
            logger.warning(f"  • {error}")

    logger.info("=" * 50)

    return result


def delete_old_folders(days_threshold=7):
    """Celery task to delete old recording folders for specified cameras.

    This task removes recording folders older than the specified threshold.
    It can accept camera IDs directly or automatically discover them from
    the recordings directory structure.

    Args:
        days_threshold (int, optional): Number of days to keep recordings.
            Folders older than this threshold will be deleted. Defaults to 7.

    Returns:
        dict: Detailed results of the cleanup operation including:
            - success (bool): Whether operation completed without errors
            - threshold_date (str): Date threshold in 'YYYY-MM-DD' format
            - days_threshold (int): Days threshold used
            - camera_ids (List[str]): Camera IDs processed
            - deleted_folders (List[dict]): Details of deleted folders
            - deleted_count (int): Number of folders deleted
            - errors (List[str]): Error messages encountered
            - error_count (int): Number of errors
            - timestamp (str): ISO timestamp of completion
    """

    logger.info("=" * 50)
    logger.info(f"НАЧАЛО ОЧИСТКИ. Порог: {days_threshold} дней")

    base_file = os.path.abspath(__file__)
    base_dir = os.path.dirname(os.path.dirname(base_file))

    recordings_base = os.path.join(base_dir, "media", "recordings")
    threshold_date = datetime.now() - timedelta(days=days_threshold)

    deleted_folders = []
    errors = []

    try:
        items = os.listdir(recordings_base)
        logger.info(f"Найдено элементов в media/recordings: {len(items)}")

        for folder_name in items:
            folder_path = os.path.join(recordings_base, folder_name)

            if not os.path.isdir(folder_path):
                logger.debug(f"ПРОПУСКАЕМ файл: {folder_name}")
                continue

            try:
                folder_date = datetime.strptime(folder_name, '%Y-%m-%d')

                if folder_date < threshold_date:
                    logger.info(f"  УДАЛЯЕМ папку: {folder_name} (дата: {folder_date.date()})")

                    try:
                        shutil.rmtree(folder_path)

                        deleted_folders.append({
                            'folder_name': folder_name,
                            'folder_date': folder_date.strftime('%Y-%m-%d'),
                            'path': folder_path,
                        })

                        logger.info(f"Папка с видео удалена: {folder_name}")

                    except PermissionError as e:
                        error_msg = f"Нет прав для удаления {folder_path}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                    except Exception as e:
                        error_msg = f"Ошибка при удалении {folder_path}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                else:
                    logger.debug(f"ОСТАВЛЯЕМ папку: {recordings_base}/{folder_name} "
                                 f"(дата: {folder_date.date()}, еще актуальна)")

            except ValueError:
                logger.debug(f"ПРОПУСКАЕМ папку: {recordings_base}/{folder_name} "
                             f"(не формат даты YYYY-MM-DD)")
                continue

    except PermissionError as e:
        error_msg = f"Нет доступа к {recordings_base}: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    except Exception as e:
        error_msg = f"Ошибка при чтении {recordings_base}: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)

    result = {
        'success': len(errors) == 0,
        'threshold_date': threshold_date.strftime('%Y-%m-%d'),
        'days_threshold': days_threshold,
        'deleted_folders': deleted_folders,
        'deleted_count': len(deleted_folders),
        'errors': errors,
        'error_count': len(errors),
        'timestamp': datetime.now().isoformat()
    }

    logger.info("\n" + "=" * 50)
    logger.info("ИТОГИ ОЧИСТКИ:")
    logger.info(f"Удалено папок: {len(deleted_folders)}")
    logger.info(f"Ошибок: {len(errors)}")

    if deleted_folders:
        logger.info("Удаление прошло успешно.")

    if errors:
        logger.warning("Ошибки:")
        for error in errors:
            logger.warning(f"{error}")

    logger.info("=" * 50)

    return result
