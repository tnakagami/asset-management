from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
  path('', views.Index.as_view(), name='index'),
  path('login/', views.LoginPage.as_view(), name='login'),
  path('logout/', views.LogoutPage.as_view(), name='logout'),
  path('profile/show/<int:pk>', views.UserProfilePage.as_view(), name='user_profile'),
  path('profile/update/<int:pk>', views.UpdateUserProfile.as_view(), name='update_profile'),
]