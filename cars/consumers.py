import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from main.models import ServiceRequest  # Adjust this import based on your project structure

class LocationConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def get_service_request(self, request_id):
        try:
            return ServiceRequest.objects.get(id=request_id)
        except ServiceRequest.DoesNotExist:
            return None

    async def has_permission(self, user, request_id):
        if not user.is_authenticated:
            return False
            
        service_request = await self.get_service_request(request_id)
        if not service_request:
            return False

        # Allow access if user is:
        # - The customer who created the request
        # - The assigned concierge
        # - A dealer or owner
        return (
            user == service_request.customer or 
            user == service_request.assigned_to or 
            user.role in ['dealer', 'owner']
        )

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

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # Forward the location data to the group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'location_update',
                    'lat': data.get('lat'),
                    'lng': data.get('lng')
                }
            )
        except json.JSONDecodeError:
            print("Error decoding JSON data")
        except Exception as e:
            print(f"Error in receive: {str(e)}")

    async def location_update(self, event):
        # Send location update to WebSocket
        await self.send(text_data=json.dumps({
            'lat': event['lat'],
            'lng': event['lng']
        }))
