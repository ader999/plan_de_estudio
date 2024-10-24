"""
URL configuration for plan_de_estudio project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from plan_de_estudio import views
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    #path('admin/', admin.site.urls),
    path('',views.inicio, name='inicio'),
    path('acerca/', views.acerca_de, name='acerca'),
    path('admin/',admin.site.urls,),
    path('login/', views.login_view, name='login'),
    path('plan_de_estudio/',views.plan_estudio, name= 'plan_de_estudio'),
    path('detalle_silabo/',views.detalle_silabo,name='detalle_silabo'),
    path('generar_excel/', views.generar_excel, name='generar_excel'),
    path('generar_docx/', views.generar_docx, name='generar_docx'),
    path('logout/', views.logout_view, name='logout'),
    path('llenar_silabo/<int:asignacion_id>/', views.llenar_silabo, name='llenar_silabo'),
    path('agregar_estudio_independiente/', views.agregar_estudio_independiente, name='agregar_estudio_independiente'),
    path('success_view/', views.success_view, name='success_view'),
    path('generar-silabo/', views.generar_silabo, name='generar_silabo')

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
