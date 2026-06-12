from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from starscream.api.schemas import TaxonomyNodeOut
from starscream.db.models import TaxonomyNode
from starscream.db.session import get_db

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


def _index_by_parent(nodes: list[TaxonomyNode]) -> dict[str | None, list[TaxonomyNode]]:
    by_parent: dict[str | None, list[TaxonomyNode]] = {}
    for node in nodes:
        by_parent.setdefault(node.parent_code, []).append(node)
    for children in by_parent.values():
        children.sort(key=lambda n: n.code)
    return by_parent


def _node_out(node: TaxonomyNode, by_parent: dict[str | None, list[TaxonomyNode]]) -> TaxonomyNodeOut:
    return TaxonomyNodeOut(
        code=node.code,
        label=node.label,
        parent_code=node.parent_code,
        description=node.description,
        recording_count=node.recording_count,
        children=[_node_out(child, by_parent) for child in by_parent.get(node.code, [])],
    )


def _build_tree(nodes: list[TaxonomyNode], parent_code: str | None = None) -> list[TaxonomyNodeOut]:
    by_parent = _index_by_parent(nodes)
    return [_node_out(node, by_parent) for node in by_parent.get(parent_code, [])]


@router.get("", response_model=list[TaxonomyNodeOut])
def get_taxonomy_tree(db: Session = Depends(get_db)):
    nodes = db.execute(select(TaxonomyNode)).scalars().all()
    return _build_tree(nodes)


@router.get("/{code}", response_model=TaxonomyNodeOut)
def get_taxonomy_subtree(code: str, db: Session = Depends(get_db)):
    nodes = db.execute(select(TaxonomyNode)).scalars().all()
    node = next((n for n in nodes if n.code == code), None)
    if not node:
        raise HTTPException(status_code=404, detail="Taxonomy code not found")
    return TaxonomyNodeOut(
        code=node.code,
        label=node.label,
        parent_code=node.parent_code,
        description=node.description,
        recording_count=node.recording_count,
        children=_build_tree(nodes, node.code),
    )
