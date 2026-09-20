from decimal import Decimal
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Category, Product, Order, OrderItem,Employee
from .serializers import (
    CategorySerializer, 
    ProductSerializer, 
    StockUpdateSerializer, 
    OrderSerializer,
    EmployeeSerializer
)


# CATEGORY
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


# PRODUCTS 
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)  # Supports file uploads and JSON

    # GET /api/products/low_stock/
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        threshold = int(request.query_params.get('threshold', 10))
        low_stock_products = Product.objects.filter(stock__lte=threshold)
        serializer = self.get_serializer(low_stock_products, many=True)
        return Response(serializer.data)

    # PATCH /api/products/<id>/update_stock/
    @action(detail=True, methods=['patch'], serializer_class=StockUpdateSerializer)
    def update_stock(self, request, pk=None):
        product = self.get_object()
        serializer = StockUpdateSerializer(product, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ORDERS
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by('-created_at')
    serializer_class = OrderSerializer

    # POST /api/orders/<id>/confirm/
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        order = self.get_object()
        if order.status == 'CANCELLED':
            return Response(
                {"error": "Cannot confirm a cancelled order."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = 'COMPLETED'
        order.save()
        return Response({"message": f"Order #{order.id} confirmed successfully.", "status": order.status})

    # POST /api/orders/<id>/cancel/
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status == 'CANCELLED':
            return Response({"message": "Order is already cancelled."})
        
        # Restore stock on cancellation
        for item in order.items.all():
            item.product.stock += item.quantity
            item.product.save()

        order.status = 'CANCELLED'
        order.save()
        return Response({"message": f"Order #{order.id} cancelled and stock restored."})

#  DASHBOARD
class DashboardAPIView(APIView):
    """
    GET /api/dashboard/
    Returns aggregated metrics: sales summary, total sales amount, total stock, and low stock products.
    """
    def get(self, request, format=None):
        # 1. Low Stock Threshold (default = 10 units)
        threshold = int(request.query_params.get('threshold', 10))

        # 2. Total Stock across all active products
        total_stock_count = Product.objects.filter(is_active=True).aggregate(
            total_units=Sum('stock')
        )['total_units'] or 0

        # 3. Total Sales & Completed Orders Count
        completed_orders = Order.objects.filter(status='COMPLETED')
        total_sales_amount = completed_orders.aggregate(
            total_revenue=Sum('total_amount')
        )['total_revenue'] or Decimal('0.00')

        completed_orders_count = completed_orders.count()

        # 4. Low Stock Product List
        low_stock_qs = Product.objects.filter(is_active=True, stock__lte=threshold)
        low_stock_products = ProductSerializer(low_stock_qs, many=True).data

        # 5. Sales Report per Product
        sales_by_product = (
            OrderItem.objects.filter(order__status='COMPLETED')
            .values('product__id', 'product__name')
            .annotate(
                total_quantity_sold=Sum('quantity'),
                total_revenue=Sum(
                    ExpressionWrapper(
                        F('quantity') * F('price'), 
                        output_field=DecimalField()
                    )
                )
            )
            .order_by('-total_quantity_sold')
        )

        return Response({
            "overview": {
                "total_sales_amount": total_sales_amount,
                "completed_orders_count": completed_orders_count,
                "total_stock_units": total_stock_count,
                "low_stock_count": len(low_stock_products)
            },
            "sales_report": sales_by_product,
            "low_stock_products": low_stock_products
        }, status=status.HTTP_200_OK)
    
# EMPLOYEES
class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        queryset = Employee.objects.all()
        role = self.request.query_params.get('role')
        designation = self.request.query_params.get('designation')

        if role:
            queryset = queryset.filter(role__iexact=role)
        if designation:
            queryset = queryset.filter(designation__icontains=designation)

        return queryset