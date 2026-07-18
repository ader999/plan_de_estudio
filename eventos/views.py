from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, Avg
from django.http import Http404

from .models import Evento, CriterioEvaluacion, JuradoEvento, Participante, Evaluacion
from .forms import EventoForm, CriterioEvaluacionForm, ParticipanteForm, EvaluacionForm

@login_required
def lista_eventos(request):
    ahora = timezone.now()
    # Eventos activos
    eventos_activos = Evento.objects.filter(fecha_inicio__lte=ahora, fecha_fin__gte=ahora)
    # Eventos futuros
    eventos_proximos = Evento.objects.filter(fecha_inicio__gt=ahora)
    # Eventos finalizados
    eventos_finalizados = Evento.objects.filter(fecha_fin__lt=ahora)
    
    # Nombre de usuario para la plantilla base
    nombre_de_usuario = request.user.get_full_name() or request.user.username

    context = {
        'eventos_activos': eventos_activos,
        'eventos_proximos': eventos_proximos,
        'eventos_finalizados': eventos_finalizados,
        'usuario': nombre_de_usuario,
        'ahora': ahora,
    }
    return render(request, 'eventos/lista.html', context)


@login_required
def crear_evento(request):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    if request.method == 'POST':
        form = EventoForm(request.POST, request.FILES)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.creado_por = request.user
            evento.save()
            messages.success(request, f"El evento '{evento.nombre}' ha sido creado exitosamente.")
            return redirect('eventos:detalle_evento', evento_id=evento.id)
    else:
        form = EventoForm()

    return render(request, 'eventos/form_evento.html', {
        'form': form,
        'titulo': 'Crear Evento',
        'usuario': nombre_de_usuario
    })


@login_required
def editar_evento(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    
    # Solo el creador o un superusuario puede editar
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para editar este evento.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    if request.method == 'POST':
        form = EventoForm(request.POST, request.FILES, instance=evento)
        if form.is_valid():
            form.save()
            messages.success(request, f"El evento '{evento.nombre}' ha sido actualizado.")
            return redirect('eventos:detalle_evento', evento_id=evento.id)
    else:
        form = EventoForm(instance=evento)

    return render(request, 'eventos/form_evento.html', {
        'form': form,
        'titulo': 'Editar Evento',
        'usuario': nombre_de_usuario,
        'evento': evento
    })


@login_required
def eliminar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    
    # Solo el creador o un superusuario puede eliminar
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para eliminar este evento.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    if request.method == 'POST':
        evento.delete()
        messages.success(request, "El evento ha sido eliminado permanentemente.")
        return redirect('eventos:lista_eventos')
        
    return render(request, 'eventos/confirmar_eliminar.html', {
        'objeto': evento,
        'tipo': 'evento',
        'usuario': request.user.get_full_name() or request.user.username
    })


@login_required
def detalle_evento(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    criterios = evento.criterios.all()
    participantes = evento.participantes.all()
    jurados = evento.jurados.all()
    
    # Comprobar si el usuario actual es jurado del evento
    es_jurado = JuradoEvento.objects.filter(evento=evento, usuario=request.user).exists()
    
    # Comprobar si el usuario es creador o administrador
    es_administrador = (evento.creado_por == request.user) or request.user.is_superuser

    context = {
        'evento': evento,
        'criterios': criterios,
        'participantes': participantes,
        'jurados': jurados,
        'es_jurado': es_jurado,
        'es_administrador': es_administrador,
        'usuario': nombre_de_usuario,
    }
    return render(request, 'eventos/detalle.html', context)


@login_required
def gestionar_criterios(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para gestionar criterios en este evento.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    criterios = evento.criterios.all()

    if request.method == 'POST':
        form = CriterioEvaluacionForm(request.POST)
        if form.is_valid():
            criterio = form.save(commit=False)
            criterio.evento = evento
            criterio.save()
            messages.success(request, f"Criterio '{criterio.nombre}' agregado con éxito.")
            return redirect('eventos:gestionar_criterios', evento_id=evento.id)
    else:
        form = CriterioEvaluacionForm()

    return render(request, 'eventos/gestionar_criterios.html', {
        'evento': evento,
        'criterios': criterios,
        'form': form,
        'usuario': nombre_de_usuario
    })


@login_required
def eliminar_criterio(request, criterio_id):
    criterio = get_object_or_404(CriterioEvaluacion, id=criterio_id)
    evento = criterio.evento
    
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para eliminar este criterio.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    criterio.delete()
    messages.success(request, "Criterio de evaluación eliminado.")
    return redirect('eventos:gestionar_criterios', evento_id=evento.id)


@login_required
def gestionar_participantes(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para gestionar participantes.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    participantes = evento.participantes.all()

    if request.method == 'POST':
        form = ParticipanteForm(request.POST)
        if form.is_valid():
            participante = form.save(commit=False)
            participante.evento = evento
            participante.save()
            messages.success(request, f"Proyecto/Equipo '{participante.nombre}' agregado exitosamente.")
            return redirect('eventos:gestionar_participantes', evento_id=evento.id)
    else:
        form = ParticipanteForm()

    return render(request, 'eventos/gestionar_participantes.html', {
        'evento': evento,
        'participantes': participantes,
        'form': form,
        'usuario': nombre_de_usuario
    })


@login_required
def eliminar_participante(request, participante_id):
    participante = get_object_or_404(Participante, id=participante_id)
    evento = participante.evento
    
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para eliminar este participante.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    participante.delete()
    messages.success(request, "Participante eliminado del evento.")
    return redirect('eventos:gestionar_participantes', evento_id=evento.id)


@login_required
def gestionar_jurado(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    
    if not evento.requiere_jurado:
        messages.warning(request, "Este evento está configurado para no requerir jurado.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para gestionar el jurado.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    jurados = evento.jurados.all()
    # IDs de usuarios ya asignados como jurado
    jurados_user_ids = jurados.values_list('usuario_id', flat=True)
    
    # Usuarios disponibles para ser jurado (excluyendo a los ya asignados)
    usuarios_disponibles = User.objects.exclude(id__in=jurados_user_ids).order_by('first_name', 'username')

    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        if usuario_id:
            usuario = get_object_or_404(User, id=usuario_id)
            JuradoEvento.objects.get_or_create(evento=evento, usuario=usuario)
            messages.success(request, f"El usuario {usuario.get_full_name() or usuario.username} ha sido asignado como jurado.")
            return redirect('eventos:gestionar_jurado', evento_id=evento.id)

    return render(request, 'eventos/gestionar_jurado.html', {
        'evento': evento,
        'jurados': jurados,
        'usuarios_disponibles': usuarios_disponibles,
        'usuario': nombre_de_usuario
    })


@login_required
def eliminar_jurado(request, jurado_id):
    jurado = get_object_or_404(JuradoEvento, id=jurado_id)
    evento = jurado.evento
    
    if evento.creado_por != request.user and not request.user.is_superuser:
        messages.error(request, "No tienes permisos para eliminar jurados.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    nombre_jurado = jurado.usuario.get_full_name() or jurado.usuario.username
    jurado.delete()
    messages.success(request, f"{nombre_jurado} ha sido removido del jurado.")
    return redirect('eventos:gestionar_jurado', evento_id=evento.id)


@login_required
def evaluar_participantes(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    
    # Verificar si es jurado
    es_jurado = JuradoEvento.objects.filter(evento=evento, usuario=request.user).exists()
    if not es_jurado and not request.user.is_superuser:
        messages.error(request, "No estás registrado como jurado de este evento.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    # Verificar si el evento está activo en fechas
    ahora = timezone.now()
    if ahora < evento.fecha_inicio:
        messages.error(request, "El evento aún no ha iniciado.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)
    elif ahora > evento.fecha_fin:
        messages.error(request, "El evento ya ha finalizado, no se permiten más evaluaciones.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    participantes = evento.participantes.all()
    criterios = evento.criterios.all()

    # Si no hay criterios creados
    if not criterios.exists():
        messages.warning(request, "Este evento no tiene criterios de evaluación definidos.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    # Encontrar qué participantes ya evaluó el usuario
    participantes_evaluados = []
    for participante in participantes:
        # Contar si el jurado tiene evaluaciones para todos los criterios de este participante
        num_evaluaciones = Evaluacion.objects.filter(
            jurado=request.user, 
            participante=participante, 
            criterio__evento=evento
        ).count()
        
        if num_evaluaciones == criterios.count() and criterios.count() > 0:
            participante.estado_evaluacion = 'Completado'
        elif num_evaluaciones > 0:
            participante.estado_evaluacion = 'Incompleto'
        else:
            participante.estado_evaluacion = 'Pendiente'

    return render(request, 'eventos/evaluar_lista.html', {
        'evento': evento,
        'participantes': participantes,
        'usuario': nombre_de_usuario
    })


@login_required
def evaluar_proyecto(request, evento_id, participante_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    participante = get_object_or_404(Participante, id=participante_id, evento=evento)
    
    es_jurado = JuradoEvento.objects.filter(evento=evento, usuario=request.user).exists()
    if not es_jurado and not request.user.is_superuser:
        messages.error(request, "No estás registrado como jurado de este evento.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    ahora = timezone.now()
    if ahora < evento.fecha_inicio or ahora > evento.fecha_fin:
        messages.error(request, "Las evaluaciones están cerradas para este evento.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    criterios = evento.criterios.all()
    if not criterios.exists():
        messages.error(request, "El evento no tiene criterios definidos.")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    # Obtener evaluaciones previas si existen
    evaluaciones_previas = Evaluacion.objects.filter(jurado=request.user, participante=participante)
    evaluaciones_existentes = {ev.criterio_id: ev.puntaje for ev in evaluaciones_previas}

    if request.method == 'POST':
        form = EvaluacionForm(request.POST, criterios=criterios, evaluaciones_existentes=evaluaciones_existentes)
        if form.is_valid():
            for criterio in criterios:
                field_name = f'criterio_{criterio.id}'
                puntaje = form.cleaned_data[field_name]
                
                # Crear o actualizar evaluación
                Evaluacion.objects.update_or_create(
                    jurado=request.user,
                    participante=participante,
                    criterio=criterio,
                    defaults={'puntaje': puntaje}
                )
            messages.success(request, f"Evaluación guardada exitosamente para '{participante.nombre}'.")
            return redirect('eventos:evaluar_participantes', evento_id=evento.id)
    else:
        form = EvaluacionForm(criterios=criterios, evaluaciones_existentes=evaluaciones_existentes)

    return render(request, 'eventos/evaluar_proyecto.html', {
        'evento': evento,
        'participante': participante,
        'form': form,
        'usuario': nombre_de_usuario
    })


@login_required
def resultados_evento(request, evento_id):
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    evento = get_object_or_404(Evento, id=evento_id)
    ahora = timezone.now()

    # Comprobar permisos: Resultados públicos solo al finalizar el evento.
    # El creador del evento o superusuario pueden verlo en cualquier momento (previsualización).
    es_administrador = (evento.creado_por == request.user) or request.user.is_superuser
    
    if ahora <= evento.fecha_fin and not es_administrador:
        messages.warning(request, f"Los resultados estarán disponibles públicamente una vez que finalice el evento (después de {evento.fecha_fin}).")
        return redirect('eventos:detalle_evento', evento_id=evento.id)

    participantes = evento.participantes.all()
    criterios = evento.criterios.all()
    jurados = evento.jurados.all()
    
    # Calcular clasificaciones y puntajes
    resultados = []
    
    for participante in participantes:
        # Puntajes agrupados por jurado
        evaluaciones_participante = Evaluacion.objects.filter(participante=participante)
        
        # Calcular total de puntos por cada jurado que evaluó
        # Estructura: {jurado_id: sum_puntaje}
        jurados_evaluadores = evaluaciones_participante.values('jurado').annotate(total_score=Sum('puntaje'))
        
        scores_list = [item['total_score'] for item in jurados_evaluadores]
        promedio_final = sum(scores_list) / len(scores_list) if scores_list else 0.0
        
        # Desglose por criterio para tabla detallada
        desglose_criterios = {}
        for criterio in criterios:
            promedio_criterio = evaluaciones_participante.filter(criterio=criterio).aggregate(Avg('puntaje'))['puntaje__avg'] or 0.0
            desglose_criterios[criterio.id] = round(promedio_criterio, 2)

        resultados.append({
            'participante': participante,
            'puntaje_promedio': round(promedio_final, 2),
            'evaluadores_count': len(scores_list),
            'desglose_criterios': desglose_criterios
        })

    # Ordenar los resultados por puntaje promedio descendente
    resultados = sorted(resultados, key=lambda x: x['puntaje_promedio'], reverse=True)

    # Añadir puesto en la clasificación
    for i, res in enumerate(resultados):
        res['puesto'] = i + 1

    context = {
        'evento': evento,
        'criterios': criterios,
        'resultados': resultados,
        'es_previsualizacion': ahora <= evento.fecha_fin,
        'usuario': nombre_de_usuario
    }
    
    return render(request, 'eventos/resultados.html', context)
