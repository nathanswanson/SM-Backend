import asyncio
from collections.abc import AsyncGenerator
from functools import cached_property
from typing import Annotated, cast


import strawberry
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL
from strawberry.fastapi import GraphQLRouter, BaseContext
from server_manager.webservice.db_models import UsersRead
from server_manager.webservice.interface.interface import ControllerStreamingInterface
from server_manager.webservice.interface.kubernetes_api.streaming_api import KubernetesStreamingAPI
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.models import Metrics
from server_manager.webservice.util.auth import verify_token, get_key
from server_manager.webservice.util.data_access import DB
from fastapi import HTTPException, status

# Initialize the streaming interface (can be swapped for Docker implementation)
# To use Docker: from server_manager.webservice.interface.docker_api.streaming_api import DockerStreamingAPI
# streaming_api: ControllerStreamingInterface = DockerStreamingAPI()
streaming_api: ControllerStreamingInterface = KubernetesStreamingAPI()


@strawberry.experimental.pydantic.type(model=Metrics, all_fields=True)
class MetricsQL:
    pass

@strawberry.experimental.pydantic.type(model=UsersRead, all_fields=True)
class UsersReadQL:
    pass

class Context(BaseContext):
    @cached_property
    def user(self) -> UsersReadQL | None:
        authorization = None

        sm_logger.debug("Authenticating user from context.")
        
        # Check HTTP headers first (for queries/mutations)
        if self.request:
            authorization = self.request.headers.get("Authorization", None)
        sm_logger.debug(f"Authorization header: {authorization}")
        sm_logger.debug(f"Connection params: {self.connection_params}")
        
        # Check WebSocket connection params (for subscriptions)
        if not authorization and self.connection_params:
            # Try common key variations for authorization in connection params
            authorization = (
                self.connection_params.get("Authorization") or
                self.connection_params.get("authorization") or
                self.connection_params.get("authToken") or
                self.connection_params.get("token")
            )
            # Handle nested headers structure: { headers: { Authorization: "..." } }
            if not authorization and isinstance(self.connection_params.get("headers"), dict):
                headers = self.connection_params["headers"]
                authorization = headers.get("Authorization") or headers.get("authorization")
            sm_logger.debug(f"Authorization from connection_params: {authorization}")
        
        if not authorization:
            return None
        
        # Extract token from "Bearer <token>"
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        token = parts[1]
        
        try:
            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate User",
                headers={"WWW-Authenticate": "Bearer"},
            )
            payload = verify_token(token, credentials_exception)
            username = payload.get("sub")
            if not username:
                return None
            
            user = DB().lookup_username(username)
            
            return UsersReadQL.from_pydantic(cast(UsersRead, user)) if user else None
        except HTTPException:
            return None

@strawberry.type
class Query:
    @strawberry.field
    def get_authenticated_user(self, info: strawberry.Info[Context]) -> UsersReadQL | None:
        return info.context.user
    
        

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def get_metrics(self, container_name: str, info: strawberry.Info[Context]) -> AsyncGenerator[MetricsQL, None]:
        if not container_name:
            return
        try:
            if not info.context.user:
                sm_logger.debug("Unauthenticated user attempted to subscribe to metrics.")
                return
            async for metric in streaming_api.stream_metrics(container_name, f"tenant-{UsersReadQL.to_pydantic(info.context.user).id}"):
                yield MetricsQL(
                    cpu=metric.cpu,
                    memory=metric.memory,
                    disk=metric.disk,
                    network=metric.network,
                )
        except TimeoutError:
            sm_logger.debug(f"Metrics subscription for container {container_name} timed out.")
        except asyncio.CancelledError:
            sm_logger.debug(f"Metrics subscription for container {container_name} was cancelled.")

    @strawberry.subscription
    async def get_logs(self, container_name: str, info: strawberry.Info[Context]) -> AsyncGenerator[str, None]:
        if not container_name:
            return
        if not info.context.user:
            sm_logger.debug("Unauthenticated user attempted to subscribe to logs.")
            return
        try:
            # Get historical logs first (non-follow mode)
            async for log_chunk in streaming_api.stream_logs(container_name, f"tenant-{UsersReadQL.to_pydantic(info.context.user).id}", tail=100, follow=False):
                yield log_chunk

            # Stream new logs
            async for line in streaming_api.stream_logs(container_name, f"tenant-{UsersReadQL.to_pydantic(info.context.user).id}", tail=1, follow=True):
                yield line
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            sm_logger.debug(f"Log subscription for container {container_name} was cancelled.")






async def get_context() -> Context:
    return Context()
        

schema = strawberry.Schema(query=Query, subscription=Subscription)
router = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphql_ide="graphiql",
    allow_queries_via_get=True,
    subscription_protocols=[GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL],
)
