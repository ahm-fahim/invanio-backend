from django.db import transaction
from rest_framework import serializers
from .models import Category, Product, Order, OrderItem

# CATEGORY
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']

# PRODUCTS
class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'category_name', 'name', 'description', 
            'regular_price', 'discount_price', 'stock', 'sizes', 
            'image', 'image_url', 'is_active', 'created_at', 'updated_at'
        ]

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

# ORDERS
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'customer_name', 'status', 'created_at', 'items']

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # 1. Validate stock availability for all items first
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            if product.stock < quantity:
                raise serializers.ValidationError(
                    f"Insufficient stock for '{product.name}'. Available: {product.stock}, Requested: {quantity}"
                )

        # 2. Create the Order
        order = Order.objects.create(**validated_data)

        # 3. Create OrderItems and deduct Product stock
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            OrderItem.objects.create(order=order, **item_data)
            
            # Deduct stock
            product.stock -= quantity
            product.save()

        return order

# STOCK
class StockUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'stock']
        read_only_fields = ['id', 'name']