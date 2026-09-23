from django.db import models


class Product(models.Model):

    category = models.ForeignKey(
        'customadmin.Category',
        on_delete=models.CASCADE,
        related_name='products'
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField()

    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    color = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    size = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    product_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    quantity = models.PositiveIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    is_deleted = models.BooleanField(
        default=False
    )

    featured = models.BooleanField(
        default=False
    )

    main_image = models.ForeignKey(
        'ProductImage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='main_for_products'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name


class ProductImage(models.Model):

    IMAGE_TYPES = (
        ('main', 'Main'),
        ('front', 'Front'),
        ('side', 'Side'),
        ('back', 'Back'),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image_type = models.CharField(
        max_length=20,
        choices=IMAGE_TYPES
    )

    image = models.ImageField(
        upload_to='products/'
    )

    position = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['position', 'id']

        constraints = [
            models.UniqueConstraint(
                fields=['product', 'image_type'],
                name='unique_product_image_type'
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.image_type}"



class ProductVariant(models.Model):

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )

    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    color = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    size = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    product_code = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True
    )

    quantity = models.PositiveIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        variant_info = []

        if self.color:
            variant_info.append(self.color)

        if self.size:
            variant_info.append(self.size)

        if variant_info:
            return f"{self.product.name} - {' / '.join(variant_info)}"

        return self.product.name

class ProductVariantImage(models.Model):

    IMAGE_TYPES = (
        ('main', 'Main'),
        ('front', 'Front'),
        ('side', 'Side'),
        ('back', 'Back'),
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image_type = models.CharField(
        max_length=20,
        choices=IMAGE_TYPES
    )

    image = models.ImageField(
        upload_to='product_variants/'
    )

    position = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['position', 'id']

        constraints = [
            models.UniqueConstraint(
                fields=['variant', 'image_type'],
                name='unique_variant_image_type'
            )
        ]

    def __str__(self):
        return f"{self.variant} - {self.image_type}"
