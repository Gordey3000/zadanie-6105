from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from .models import Organization, Tender, Proposal, Employee, TenderVersion, ProposalVersion
from .serializers import OrganizationSerializer, TenderSerializer, ProposalSerializer, EmployeeSerializer, UserSerializer
from rest_framework.views import APIView

# Ping для проверки
def ping(request):
    return HttpResponse("ok")

# Вьюсет для организации
class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    # Создание новой организации
    @action(detail=False, methods=['post'], url_path='new')
    def new(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        organization = Organization.objects.create(
            name=request.data['name'],
            description=request.data['description'],
            type=request.data['type']
        )

        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)

# Вьюсет для тендеров
class TenderViewSet(viewsets.ModelViewSet):
    queryset = Tender.objects.all()
    serializer_class = TenderSerializer
    filter_backends = [filters.OrderingFilter]
    permission_classes = [IsAuthenticated]
    ordering_fields = '__all__'

    # Список тендеров с фильтрацией и сортировкой
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        service_type = request.query_params.get('service_type')
        if service_type:
            queryset = queryset.filter(service_type=service_type)

        ordering = request.query_params.get('ordering')
        if ordering:
            queryset = queryset.order_by(ordering)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Создание нового тендера
    @action(detail=False, methods=['post'], url_path='new')
    def new(self, request):
        organization_id = request.data.get('organization')
        if not organization_id:
            return Response({"detail": "Organization ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=status.HTTP_400_BAD_REQUEST)

        tender = Tender.objects.create(
            title=request.data['title'],
            description=request.data['description'],
            service_type=request.data['service_type'],
            status=request.data['status'],
            organization=organization
        )

        return Response(TenderSerializer(tender).data, status=status.HTTP_201_CREATED)

    # Тендеры текущего пользователя
    @action(detail=False, methods=['get'], url_path='my')
    def my(self, request):
        try:
            employee = request.user.employee
            organization = employee.organization
        except Employee.DoesNotExist:
            return Response({"detail": "User does not belong to any organization."}, status=status.HTTP_400_BAD_REQUEST)

        tenders = Tender.objects.filter(organization=organization)
        serializer = self.get_serializer(tenders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Обновление статуса тендера
    @action(detail=True, methods=['post'], url_path='status')
    def status(self, request, pk=None):
        tender = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(Tender.STATUS_CHOICES):
            tender.status = new_status
            tender.save()
            return Response({"status": tender.status}, status=status.HTTP_200_OK)
        return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

    # Редактирование тендера
    @action(detail=True, methods=['patch'], url_path='edit')
    def edit_tender(self, request, pk=None):
        tender = self.get_object()

        try:
            employee = request.user.employee
            organization = employee.organization
        except Employee.DoesNotExist:
            return Response({"detail": "User does not belong to any organization."}, status=status.HTTP_400_BAD_REQUEST)

        if tender.organization != organization:
            return Response({"detail": "You do not have permission to edit this tender."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        tender.title = data.get('title', tender.title)
        tender.description = data.get('description', tender.description)
        tender.service_type = data.get('service_type', tender.service_type)
        tender.status = data.get('status', tender.status)

        tender.version += 1
        tender.save()

        TenderVersion.objects.create(
            tender=tender,
            title=tender.title,
            description=tender.description,
            status=tender.status,
            service_type=tender.service_type,
            version=tender.version
        )

        return Response(TenderSerializer(tender).data, status=status.HTTP_200_OK)

    # Откат версии тендера
    @action(detail=True, methods=['put'], url_path=r'rollback/(?P<version>\d+)')
    def rollback_tender(self, request, pk=None, version=None):
        tender = self.get_object()

        try:
            tender_version = TenderVersion.objects.get(tender=tender, version=version)
        except TenderVersion.DoesNotExist:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        # Восстановление состояния тендера
        tender.title = tender_version.title
        tender.description = tender_version.description
        tender.status = tender_version.status
        tender.service_type = tender_version.service_type
        tender.version = tender_version.version
        tender.save()

        return Response(TenderSerializer(tender).data, status=status.HTTP_200_OK)

# Вьюсет для предложений
class ProposalViewSet(viewsets.ModelViewSet):
    queryset = Proposal.objects.all()
    serializer_class = ProposalSerializer
    permission_classes = [IsAuthenticated]

    # Создание предложения
    @action(detail=False, methods=['post'], url_path='new')
    def new(self, request):
        tender_id = request.data.get('tenderId')
        organization_id = request.data.get('organizationId')

        if not tender_id or not organization_id:
            return Response({"detail": "Tender ID and Organization ID are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tender = Tender.objects.get(id=tender_id)
        except Tender.DoesNotExist:
            return Response({"detail": "Tender not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

        proposal = Proposal.objects.create(
            tender=tender,
            organization=organization,
            status=request.data.get('status', 'CREATED')
        )

        return Response(ProposalSerializer(proposal).data, status=status.HTTP_201_CREATED)

    # Список предложений текущего пользователя
    @action(detail=False, methods=['get'], url_path='my')
    def my_bids(self, request):
        try:
            employee = request.user.employee
            organization = employee.organization
        except Employee.DoesNotExist:
            return Response({"detail": "User does not belong to any organization."}, status=status.HTTP_400_BAD_REQUEST)

        proposals = Proposal.objects.filter(organization=organization)
        serializer = self.get_serializer(proposals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Список предложений для тендера
    @action(detail=False, methods=['get'], url_path=r'(?P<tender_id>[^/.]+)/list')
    def list_bids_for_tender(self, request, tender_id=None):
        try:
            tender = Tender.objects.get(id=tender_id)
        except Tender.DoesNotExist:
            return Response({"detail": "Tender not found."}, status=status.HTTP_404_NOT_FOUND)

        proposals = Proposal.objects.filter(tender=tender)
        serializer = self.get_serializer(proposals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Редактирование предложения
    @action(detail=True, methods=['patch'], url_path='edit')
    def edit_bid(self, request, pk=None):
        proposal = self.get_object()

        # Проверка прав на редактирование предложения
        employee = request.user.employee
        if proposal.organization != employee.organization:
            return Response({"detail": "You do not have permission to edit this proposal."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data

        # Создание новой версии предложения
        ProposalVersion.objects.create(
            proposal=proposal,
            status=proposal.status,
            version=proposal.version
        )

        # Обновление предложения
        proposal.status = data.get('status', proposal.status)
        proposal.version += 1
        proposal.save()

        return Response(ProposalSerializer(proposal).data, status=status.HTTP_200_OK)

    # Откат версии предложения
    @action(detail=True, methods=['put'], url_path=r'rollback/(?P<version>\d+)')
    def rollback_bid(self, request, pk=None, version=None):
        proposal = self.get_object()

        try:
            proposal_version = ProposalVersion.objects.get(proposal=proposal, version=version)
        except ProposalVersion.DoesNotExist:
            return Response({"detail": "Version not found."}, status=status.HTTP_404_NOT_FOUND)

        # Восстановление состояния предложения
        proposal.status = proposal_version.status
        proposal.version = proposal_version.version
        proposal.save()

        return Response(ProposalSerializer(proposal).data, status=status.HTTP_200_OK)

# Вьюсет для сотрудников
class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]

# Вью для регистрации пользователя
class RegisterUserView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            Employee.objects.create(user=user)
            return Response({'detail': 'User registered successfully.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
