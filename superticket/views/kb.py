"""Knowledge Base API endpoints (mock data)."""

from fastapi import APIRouter, HTTPException, status

from superticket.data.mock_kb import get_kb_article, search_kb
from superticket.schemas.kb import KBArticleOut

router = APIRouter(prefix="/kb", tags=["kb"])


@router.get("/search", response_model=list[KBArticleOut])
def search_articles(q: str | None = None, category: str | None = None, sub_category: str | None = None):
    """Search KB articles by query and/or category."""
    results = search_kb(query=q, category=category, sub_category=sub_category)
    return results


@router.get("/{slug}", response_model=KBArticleOut)
def get_article(slug: str):
    """Get a single KB article by slug."""
    article = get_kb_article(slug)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")
    return article
