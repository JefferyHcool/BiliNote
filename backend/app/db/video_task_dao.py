from app.db.models.video_tasks import VideoTask
from app.db.engine import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)


# 插入任务
def insert_video_task(video_id: str, platform: str, task_id: str):
    db = next(get_db())
    try:
        task = VideoTask(video_id=video_id, platform=platform, task_id=task_id)
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info(f"Video task inserted successfully. video_id: {video_id}, platform: {platform}, task_id: {task_id}")
    except Exception as e:
        logger.error(f"Failed to insert video task: {e}")
    finally:
        db.close()


# 查询任务（最新一条）
def get_task_by_video(video_id: str, platform: str):
    db = next(get_db())
    try:
        task = (
            db.query(VideoTask)
            .filter_by(video_id=video_id, platform=platform)
            .order_by(VideoTask.created_at.desc())
            .first()
        )
        if task:
            logger.info(f"Task found for video_id: {video_id} and platform: {platform}")
            return task.task_id
        else:
            logger.info(f"No task found for video_id: {video_id} and platform: {platform}")
            return None
    except Exception as e:
        logger.error(f"Failed to get task by video: {e}")
    finally:
        db.close()


# 删除任务
def delete_task_by_video(video_id: str, platform: str):
    db = next(get_db())
    try:
        tasks = (
            db.query(VideoTask)
            .filter_by(video_id=video_id, platform=platform)
            .all()
        )
        for task in tasks:
            db.delete(task)
        db.commit()
        logger.info(f"Task(s) deleted for video_id: {video_id} and platform: {platform}")
    except Exception as e:
        logger.error(f"Failed to delete task by video: {e}")
    finally:
        db.close()


def delete_task_by_task_id(task_id: str):
    db = next(get_db())
    try:
        task = db.query(VideoTask).filter_by(task_id=task_id).first()
        if task:
            db.delete(task)
            db.commit()
            logger.info(f"Task deleted by task_id: {task_id}")
            return 1
        return 0
    except Exception as e:
        logger.error(f"Failed to delete task by task_id: {e}")
        return 0
    finally:
        db.close()
