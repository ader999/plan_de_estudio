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
    path('detalle_silabo/<str:codigo>/', views.detalle_silabo, name='detalle_silabo_codigo'),
    path('guia-autodidactica/', views.guia_autodidactica, name='guia_autodidactica'),
    path('guia-autodidactica/<str:codigo>/', views.guia_autodidactica, name='guia_autodidactica_codigo'),
    path('secuencia-didactica/', views.secuencia_didactica, name='secuencia_didactica'),
    path('secuencia-didactica/<str:codigo>/', views.secuencia_didactica, name='secuencia_didactica_codigo'),
    path('generar_excel2/', views.generar_excel_original, name='generar_excel_original'),
    path('generar_excel/', views.generar_excel_original, name='generar_excel'),
    path('generar_docx/', views.generar_docx, name='generar_docx'),
    path('descargar-secuencia-didactica/', views.descargar_secuencia_didactica, name='descargar_secuencia_didactica'),
    path('logout/', views.logout_view, name='logout'),
    path('success_view/', views.success_view, name='success_view'),
    path('generar-silabo/', views.generar_silabo, name='generar_silabo'),
    path('generar-estudio-independiente/', views.generar_estudio_independiente, name='generar_estudio_independiente'),
    
    # Rutas para formularios de sílabo y guía
    path('formulario_silabo/<int:asignacion_id>/', views.ver_formulario_silabo, name='ver_formulario_silabo'),
    path('formulario_guia/<int:asignacion_id>/', views.ver_formulario_guia, name='ver_formulario_guia'),
    path('guardar_silabo/<int:asignacion_id>/', views.guardar_silabo, name='guardar_silabo'),
    path('guardar-guia/<int:silabo_id>/', views.guardar_guia, name='guardar_guia'),
    path('tutoriales/', views.vista_tutoriales, name='tutoriales'),

    # Ruta para cargar guía específica de un sílabo
    path('cargar_guia/<int:silabo_id>/', views.cargar_guia, name='cargar_guia'),
    path('silabo/actualizar/<int:silabo_id>/', views.actualizar_silabo, name='actualizar_silabo'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
