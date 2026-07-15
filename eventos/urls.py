from django.urls import path
from . import views

app_name = 'eventos'

urlpatterns = [
    path('', views.lista_eventos, name='lista_eventos'),
    path('crear/', views.crear_evento, name='crear_evento'),
    path('<int:evento_id>/', views.detalle_evento, name='detalle_evento'),
    path('<int:evento_id>/editar/', views.editar_evento, name='editar_evento'),
    path('<int:evento_id>/eliminar/', views.eliminar_evento, name='eliminar_evento'),
    
    # Criterios
    path('<int:evento_id>/criterios/', views.gestionar_criterios, name='gestionar_criterios'),
    path('criterio/eliminar/<int:criterio_id>/', views.eliminar_criterio, name='eliminar_criterio'),
    
    # Participantes (Proyectos/Equipos)
    path('<int:evento_id>/participantes/', views.gestionar_participantes, name='gestionar_participantes'),
    path('participante/eliminar/<int:participante_id>/', views.eliminar_participante, name='eliminar_participante'),
    
    # Jurado
    path('<int:evento_id>/jurado/', views.gestionar_jurado, name='gestionar_jurado'),
    path('jurado/eliminar/<int:jurado_id>/', views.eliminar_jurado, name='eliminar_jurado'),
    
    # Evaluar
    path('<int:evento_id>/evaluar/', views.evaluar_participantes, name='evaluar_participantes'),
    path('<int:evento_id>/evaluar/<int:participante_id>/', views.evaluar_proyecto, name='evaluar_proyecto'),
    
    # Resultados
    path('<int:evento_id>/resultados/', views.resultados_evento, name='resultados_evento'),
]
