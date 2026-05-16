"""/documents endpoints — protected by current_user dependency."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.repositories import document_repo
from app.schemas.document import DocumentCreated, DocumentRead
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document and index it into the vector store",
)
async def upload_document(
    user: CurrentUser,
    session: DbSession,
    file: UploadFile = File(...),
) -> DocumentCreated:
    data = await file.read()
    result = await document_service.ingest_document(
        session,
        owner_id=user.id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return DocumentCreated(**result)


@router.get(
    "",
    response_model=list[DocumentRead],
    summary="List the user's documents and their chunk counts",
)
async def list_my_documents(user: CurrentUser, session: DbSession) -> list[DocumentRead]:
    rows = await document_repo.list_documents(session, owner_id=user.id)
    return [DocumentRead(**row) for row in rows]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and all of its chunks",
)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await document_service.delete_document(session, document_id, owner_id=user.id)
