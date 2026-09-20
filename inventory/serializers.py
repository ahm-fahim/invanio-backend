from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from .models import Category, Product, Order, OrderItem, Employee

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

# ORDER ITEMS
class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    product_name = serializers.ReadOnlyField(source='product.name')
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price']

# ORDERS
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    
    total_quantity = serializers.IntegerField(read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 
            'customer_name', 
            'phone', 
            'location', 
            'delivery_location', 
            'shipping_cost', 
            'discount', 
            'total_quantity', 
            'total_amount', 
            'status', 
            'created_at', 
            'items'
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        shipping_cost = validated_data.get('shipping_cost', Decimal('0.00'))
        discount = validated_data.get('discount', Decimal('0.00'))

        calculated_total_quantity = 0
        calculated_items_total = Decimal('0.00')

        # 1. Validate stock & calculate auto-totals
        for item in items_data:
            product = item['product']
            quantity = item['quantity']

            if product.stock < quantity:
                raise serializers.ValidationError(
                    f"Insufficient stock for '{product.name}'. Available: {product.stock}, Requested: {quantity}"
                )

            # Determine price: explicitly passed price -> discount price -> regular price
            unit_price = item.get('price') or product.discount_price or product.regular_price
            item['price'] = unit_price

            calculated_total_quantity += quantity
            calculated_items_total += unit_price * quantity

        # Total Amount = Items Total + Shipping Cost - Discount
        calculated_total_amount = calculated_items_total + shipping_cost - discount

        validated_data['total_quantity'] = calculated_total_quantity
        validated_data['total_amount'] = max(Decimal('0.00'), calculated_total_amount)

        # 2. Create Order instance
        order = Order.objects.create(**validated_data)

        # 3. Create OrderItems & deduct stock
        for item in items_data:
            product = item['product']
            quantity = item['quantity']

            OrderItem.objects.create(order=order, **item)

            product.stock -= quantity
            product.save()

        return order

# STOCK
class StockUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'stock']
        read_only_fields = ['id', 'name']
    
# EMPLOYEE
class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'id', 
            'employee_id', 
            'name', 
            'address', 
            'phone', 
            'designation', 
            'salary', 
            'role', 
            'created_at', 
            'updated_at'
        ]