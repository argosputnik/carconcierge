# consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from main.models import ServiceRequest

User = get_user_model()

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
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

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Receives a message from the WebSocket.
        If the user is a concierge, update the DB and broadcast to group.
        """
        data = json.loads(text_data)
        lat = data.get('lat')
        lng = data.get('lng')

        # Only concierge can send location updates
        if self.user.role == 'concierge':
            await self.update_location(self.request_id, lat, lng)

            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'location_update',
                    'lat': lat,
                    'lng': lng,
                }
            )

    async def location_update(self, event):
        """
        Called when a location update is sent to the group.
        """
        await self.send(text_data=json.dumps({
            'lat': event['lat'],
            'lng': event['lng'],
        }))

    @database_sync_to_async
    def has_permission(self, user, request_id):
        try:
            sr = ServiceRequest.objects.get(id=request_id)
            return (
                user == sr.customer or
                user == sr.assigned_to or
                user.role in ['concierge', 'dealer', 'owner']
            )
        except ServiceRequest.DoesNotExist:
            return False

    @database_sync_to_async
    def update_location(self, request_id, lat, lng):
        try:
            sr = ServiceRequest.objects.get(id=request_id)
            sr.concierge_latitude = lat
            sr.concierge_longitude = lng
            sr.save(update_fields=['concierge_latitude', 'concierge_longitude'])
        except ServiceRequest.DoesNotExist:
            pass
