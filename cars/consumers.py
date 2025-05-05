import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.group_name = f"location_{self.request_id}"
        self.user = self.scope["user"]

        # Permission check: only allow customer, assigned_to, or staff roles
        if not await self.has_permission(self.user, self.request_id):
            await self.close()
            return

        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    # ... rest of your code ...
