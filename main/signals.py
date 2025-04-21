from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

User = get_user_model()

GROUP_TO_ROLE = {
    'owners': 'owner',
    'dealers': 'dealer',
    'concierge': 'concierge',
}

ROLE_TO_GROUP = {
    'owner': 'Owners',
    'dealer': 'Dealers',
    'concierge': 'Concierge',
}


@receiver(post_save, sender=User)
def assign_group_based_on_role(sender, instance, **kwargs):
    if instance.role:
        group_name = ROLE_TO_GROUP.get(instance.role.lower())
        if group_name:
            try:
                group = Group.objects.get(name__iexact=group_name)
                instance.groups.set([group])
                print(f"Assigned group '{group.name}' to user '{instance.username}' based on role '{instance.role}'")
            except Group.DoesNotExist:
                print(f"Group '{group_name}' not found for user '{instance.username}'")


@receiver(m2m_changed, sender=User.groups.through)
def assign_role_based_on_group(sender, instance, action, **kwargs):
    # Ensure that the instance is a User before proceeding
    if not isinstance(instance, User):
        return  # Skip if it's not a user
    
    # Only process certain actions
    if action in ['post_add', 'post_remove', 'post_clear']:
        group_names = [g.name.lower() for g in instance.groups.all()]
        for name in group_names:
            if name in GROUP_TO_ROLE:
                new_role = GROUP_TO_ROLE[name]
                if instance.role != new_role:
                    instance.role = new_role
                    instance.save()
                    print(f"Role updated to '{new_role}' based on group '{name}' for user '{instance.username}'")
                break

