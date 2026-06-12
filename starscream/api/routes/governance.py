from fastapi import APIRouter

from starscream.governance.policies import get_governance_summary

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("")
def get_governance():
    """Return a JSON summary of Starscream Foundation governance policies."""
    return get_governance_summary()
