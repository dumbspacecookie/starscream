from fastapi import Depends
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter

from starscream.api.graphql.schema import schema
from starscream.db.session import get_db


async def get_context(db: Session = Depends(get_db)):
    return {"db": db}


graphql_api_router = GraphQLRouter(schema, graphql_ide=None, context_getter=get_context)
graphql_ide_router = GraphQLRouter(schema, context_getter=get_context)
