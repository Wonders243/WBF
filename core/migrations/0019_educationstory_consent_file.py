from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_educationstory_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="educationstory",
            name="consent_file",
            field=models.FileField(blank=True, null=True, upload_to="stories/education/consents/%Y/%m/"),
        ),
    ]

