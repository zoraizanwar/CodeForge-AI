"""
Orchestration workflow service for CodeForge AI Agent tasks (Step 7).
Executes the end-to-end task lifecycle in background tasks:
  pending -> analyzing -> planning -> generating -> ready_for_review (or failed)
"""
import os
import uuid
import logging
import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.agent import AgentTask
from app.models.repository import Repository
from app.providers.ai.base import AIProvider
from app.providers.ai.grok import GrokProvider
from app.services.agent.context_retriever import retrieve_task_context
from app.services.agent.planner import generate_implementation_plan
from app.services.agent.code_generator import generate_code_changes

logger = logging.getLogger("codeforge.agent.orchestrator")


async def run_agent_task_pipeline(task_id: uuid.UUID, db: Session = None) -> None:
    """
    Background worker task executing the full agent pipeline for a task.
    Supports passing active DB session for testing.
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"Agent task {task_id} not found for execution.")
            return

        repo = db.query(Repository).filter(Repository.id == task.repository_id).first()
        if not repo:
            task.status = "failed"
            task.error_message = "Associated repository not found."
            db.commit()
            return

        ai_provider: AIProvider = GrokProvider()

        # Step 1: Context Retrieval (Analyzing)
        task.status = "analyzing"
        task.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        context = retrieve_task_context(db, repo, task.task_description)
        task.files_analyzed = context.files_analyzed
        db.commit()

        # Step 2: Implementation Planning (Planning)
        task.status = "planning"
        task.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        plan = await generate_implementation_plan(ai_provider, task.task_description, context)
        task.plan = plan.model_dump()
        db.commit()

        # Step 3: Code Generation & Validation (Generating)
        task.status = "generating"
        task.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        code_gen_res = await generate_code_changes(
            ai_provider=ai_provider,
            repo_local_path=repo.local_path,
            task_description=task.task_description,
            plan=plan,
            context=context
        )

        changes_list = [c.model_dump() for c in code_gen_res.changes]
        files_to_modify = list(set([c["file_path"] for c in changes_list]))

        task.changes = changes_list
        task.files_to_modify = files_to_modify
        task.status = "ready_for_review"
        task.completed_at = datetime.datetime.now(datetime.timezone.utc)
        task.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()

        # Apply patch directly to original repo workspace for instant localhost updates
        if repo.local_path and os.path.exists(repo.local_path) and changes_list:
            try:
                from app.services.execution.patch_applier import apply_task_patch
                apply_task_patch(repo.local_path, changes_list)
                logger.info(f"Instantly applied generated patch to local workspace '{repo.local_path}'.")
            except Exception as apply_err:
                logger.warning(f"Could not instantly apply patch to local workspace: {apply_err}")

        logger.info(f"Agent task {task_id} completed successfully. Status: ready_for_review.")

    except Exception as e:
        logger.error(f"Agent task pipeline failed for task {task_id}: {str(e)}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.updated_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
        except Exception as inner_e:
            logger.error(f"Failed to update task failure status: {str(inner_e)}")

    finally:
        if should_close:
            db.close()
