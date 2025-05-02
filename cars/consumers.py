# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ServiceRequest

User = get_user_model()

class LocationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.group_name = f"location_{self.request_id}"
        
        # Get the user from the scope
        user = self.scope["user"]
        
        # Check if user has permission to access this service request
        if not await self.has_permission(user, self.request_id):
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

    # Receive message from WebSocket (from concierge)
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        # Save location to database if sender is concierge
        user = self.scope["user"]
        if user.role == 'concierge':
            await self.update_location(self.request_id, data['lat'], data['lng'])
        
        # Broadcast to group
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'location_update',
                'lat': data['lat'],
                'lng': data['lng'],
            }
        )

    # Receive message from group
    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            'lat': event['lat'],
            'lng': event['lng'],
        }))
    
    @database_sync_to_async
    def has_permission(self, user, request_id):
        try:
            sr = ServiceRequest.objects.get(id=request_id)
            return (user == sr.customer or 
                    user == sr.assigned_to or 
                    user.role in ['concierge', 'dealer', 'owner'])
        except ServiceRequest.DoesNotExist:
            return False
    
    @database_sync_to_async
    def update_location(self, request_id, lat, lng):
        try:
            sr = ServiceRequest.objects.get(id=request_id)
            sr.concierge_latitude = lat
            sr.concierge_longitude = lng
            sr.save(update_fields=['concierge_latitude', 'concierge_longitude'])
            return True
        except ServiceRequest.DoesNotExist:
            return False
