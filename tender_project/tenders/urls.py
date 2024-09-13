from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, TenderViewSet, ProposalViewSet, EmployeeViewSet, ping

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet)
router.register(r'tenders', TenderViewSet)
router.register(r'bids', ProposalViewSet, basename='proposal')
router.register(r'employees', EmployeeViewSet)

urlpatterns = router.urls