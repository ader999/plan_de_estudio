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
    path('generar_excel2/', views.generar_excel_original, name='generar_excel_original'),
    path('generar_docx/', views.generar_docx, name='generar_docx'),
    path('logout/', views.logout_view, name='logout'),
    path('agregar_guia/', views.gestionar_silabo_y_guia, name='agregar_guia'),
    path('success_view/', views.success_view, name='success_view'),
    path('generar-silabo/', views.generar_silabo, name='generar_silabo'),
    path('generar_guia/', views.generar_estudio_independiente, name='generar_guia'),
    path('gestionar_silabo_y_guia/', views.gestionar_silabo_y_guia, name='gestionar_silabo_y_guia_ajax'),
    path('gestionar_silabo_y_guia/<int:id>/', views.gestionar_silabo_y_guia, name='gestionar_silabo_y_guia'),
    path('generar-silabo-view/<int:asignacion_id>/', views.gestionar_silabo_y_guia, name='guardar_silabo')

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
