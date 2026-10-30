from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_remove_product_color_remove_product_discount_price_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="main_image",
        ),
    ]
