from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Category, Product, Order
from .serializers import CategorySerializer, ProductSerializer, StockUpdateSerializer, OrderSerializer


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