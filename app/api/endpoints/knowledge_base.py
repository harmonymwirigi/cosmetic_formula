# backend/app/api/endpoints/knowledge_base.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Pydantic schemas for request/response (add to schemas.py)
class ContentCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_premium: bool = False
    is_professional: bool = False

class ContentCategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    is_premium: bool
    is_professional: bool
    
    class Config:
        from_attributes = True

class KnowledgeArticleCreate(BaseModel):
    title: str
    content: str
    excerpt: Optional[str] = None
    category_id: int
    featured_image: Optional[str] = None
    is_premium: bool = False
    is_professional: bool = False
    is_published: bool = True
    tags: List[str] = []

class KnowledgeArticleResponse(BaseModel):
    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    category_id: int
    author_id: int
    featured_image: Optional[str]
    is_premium: bool
    is_professional: bool
    is_published: bool
    view_count: int
    created_at: datetime
    tags: List[str] = []
    
    class Config:
        from_attributes = True

# Categories Endpoints
@router.get("/categories", response_model=List[ContentCategoryResponse])
async def get_categories(
    db: Session = Depends(get_db),
    parent_id: Optional[int] = None
):
    """Get all content categories, optionally filtered by parent"""
    query = db.query(models.ContentCategory)
    if parent_id is not None:
        query = query.filter(models.ContentCategory.parent_id == parent_id)
    return query.all()

@router.post("/categories", response_model=ContentCategoryResponse)
async def create_category(
    category: ContentCategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new content category (admin only)"""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create categories"
        )
    
    # Create slug from name
    import re
    slug = re.sub(r'[^\w\s-]', '', category.name.lower())
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    
    # Create new category
    db_category = models.ContentCategory(
        name=category.name,
        slug=slug,
        description=category.description,
        parent_id=category.parent_id,
        is_premium=category.is_premium,
        is_professional=category.is_professional
    )
    
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    
    return db_category

# Articles Endpoints
@router.get("/articles", response_model=List[KnowledgeArticleResponse])
async def get_articles(
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20,
    category_id: Optional[int] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None
):
    """Get articles with filtering and pagination"""
    query = db.query(models.KnowledgeArticle).filter(models.KnowledgeArticle.is_published == True)
    
    # Check access to premium/professional content
    if current_user is None or current_user.subscription_type == models.SubscriptionType.FREE:
        query = query.filter(models.KnowledgeArticle.is_premium == False, 
                             models.KnowledgeArticle.is_professional == False)
    elif current_user.subscription_type == models.SubscriptionType.PREMIUM:
        query = query.filter(models.KnowledgeArticle.is_professional == False)
    
    # Apply filters
    if category_id:
        query = query.filter(models.KnowledgeArticle.category_id == category_id)
    
    if tag:
        query = query.join(models.ArticleTags).join(models.ArticleTag).filter(
            models.ArticleTag.name == tag
        )
    
    if search:
        query = query.filter(
            models.KnowledgeArticle.title.ilike(f"%{search}%") | 
            models.KnowledgeArticle.content.ilike(f"%{search}%")
        )
    
    # Order by newest first
    query = query.order_by(models.KnowledgeArticle.created_at.desc())
    
    # Apply pagination
    articles = query.offset(skip).limit(limit).all()
    
    # Format response
    result = []
    for article in articles:
        # Get tags
        tags = [tag.name for tag in db.query(models.ArticleTag).join(
            models.ArticleTags
        ).filter(models.ArticleTags.article_id == article.id).all()]
        
        # Create response object
        article_dict = {
            "id": article.id,
            "title": article.title,
            "slug": article.slug,
            "excerpt": article.excerpt,
            "content": article.content if current_user else article.excerpt,
            "category_id": article.category_id,
            "author_id": article.author_id,
            "featured_image": article.featured_image,
            "is_premium": article.is_premium,
            "is_professional": article.is_professional,
            "is_published": article.is_published,
            "view_count": article.view_count,
            "created_at": article.created_at,
            "tags": tags
        }
        result.append(article_dict)
    
    return result

@router.get("/articles/{slug}", response_model=KnowledgeArticleResponse)
async def get_article(
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user)
):
    """Get a single article by slug"""
    article = db.query(models.KnowledgeArticle).filter(
        models.KnowledgeArticle.slug == slug,
        models.KnowledgeArticle.is_published == True
    ).first()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    # Check access to premium/professional content
    if article.is_professional and (not current_user or current_user.subscription_type != models.SubscriptionType.PROFESSIONAL):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This article requires a Professional subscription"
        )
    
    if article.is_premium and (not current_user or current_user.subscription_type == models.SubscriptionType.FREE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This article requires a Premium or Professional subscription"
        )
    
    # Increment view count
    article.view_count += 1
    db.commit()
    
    # Get tags
    tags = [tag.name for tag in db.query(models.ArticleTag).join(
        models.ArticleTags
    ).filter(models.ArticleTags.article_id == article.id).all()]
    
    # Create response
    response = {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "excerpt": article.excerpt,
        "content": article.content,
        "category_id": article.category_id,
        "author_id": article.author_id,
        "featured_image": article.featured_image,
        "is_premium": article.is_premium,
        "is_professional": article.is_professional,
        "is_published": article.is_published,
        "view_count": article.view_count,
        "created_at": article.created_at,
        "tags": tags
    }
    
    return response

@router.post("/articles", response_model=KnowledgeArticleResponse)
async def create_article(
    article: KnowledgeArticleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new knowledge article (admin or professional users)"""
    # Check if user has permission (admin or professional subscription)
    if not current_user.is_admin and current_user.subscription_type != models.SubscriptionType.PROFESSIONAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators or professional subscribers can create articles"
        )
    
    # Validate category exists
    category = db.query(models.ContentCategory).filter(
        models.ContentCategory.id == article.category_id
    ).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Create slug from title
    import re
    from datetime import datetime
    
    slug_base = re.sub(r'[^\w\s-]', '', article.title.lower())
    slug_base = re.sub(r'[\s-]+', '-', slug_base).strip('-')
    
    # Add timestamp to ensure uniqueness
    timestamp = int(datetime.now().timestamp())
    slug = f"{slug_base}-{timestamp}"
    
    # Create new article
    db_article = models.KnowledgeArticle(
        title=article.title,
        slug=slug,
        content=article.content,
        excerpt=article.excerpt or article.content[:200] + "...",
        category_id=article.category_id,
        author_id=current_user.id,
        featured_image=article.featured_image,
        is_premium=article.is_premium,
        is_professional=article.is_professional,
        is_published=article.is_published
    )
    
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    
    # Add tags
    for tag_name in article.tags:
        # Get or create tag
        tag = db.query(models.ArticleTag).filter(models.ArticleTag.name == tag_name).first()
        if not tag:
            tag = models.ArticleTag(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        
        # Create article-tag association
        article_tag = models.ArticleTags(article_id=db_article.id, tag_id=tag.id)
        db.add(article_tag)
    
    db.commit()
    
    # Prepare response
    response = {
        "id": db_article.id,
        "title": db_article.title,
        "slug": db_article.slug,
        "excerpt": db_article.excerpt,
        "content": db_article.content,
        "category_id": db_article.category_id,
        "author_id": db_article.author_id,
        "featured_image": db_article.featured_image,
        "is_premium": db_article.is_premium,
        "is_professional": db_article.is_professional,
        "is_published": db_article.is_published,
        "view_count": db_article.view_count,
        "created_at": db_article.created_at,
        "tags": article.tags
    }
    
    return response

# Tutorial Endpoints - Add similar CRUD operations for tutorials