from django.urls import re_path
from cars.consumers import LocationConsumer


# Use a late-binding approach
websocket_urlpatterns = [
   re_path(r'^ws/location/(?P<service_request_id>\d+)/$', LocationConsumer.as_asgi()),
]

