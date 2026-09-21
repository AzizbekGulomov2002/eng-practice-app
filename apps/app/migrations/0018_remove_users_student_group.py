from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0017_alter_users_managers"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="users",
            name="student_group",
        ),
    ]
