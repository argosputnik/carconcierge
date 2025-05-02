from django.urls import re_path

# Don't import consumers directly at the module level
# Instead, use string references to the consumer classes

websocket_urlpatterns = [
    re_path(r'ws/somepath/$', 'cars.consumers.MyConsumer.as_asgi()'),
]
