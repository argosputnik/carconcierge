from django.urls import re_path

# Use a late-binding approach
websocket_urlpatterns = [
    re_path(r'ws/somepath/$', lambda: __import__('cars.consumers').consumers.MyConsumer.as_asgi()),
]
