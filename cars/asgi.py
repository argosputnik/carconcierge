import os
# Set the settings module before any Django imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cars.settings')

# Now import Django and Channels components
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import your routing module after Django settings are configured
import cars.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            cars.routing.websocket_urlpatterns
        )
    ),
})
