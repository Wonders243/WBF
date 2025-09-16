from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_educationstory_educationstoryimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="educationstory",
            name="category",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("education", "Éducation"),
                    ("sante", "Santé"),
                    ("psy", "Soutien psychologique"),
                    ("autre", "Autre"),
                ],
                default="education",
            ),
        ),
        migrations.AddIndex(
            model_name="educationstory",
            index=models.Index(fields=["category", "is_published", "created_at"], name="core_story_cat_pub_idx"),
        ),
    ]

